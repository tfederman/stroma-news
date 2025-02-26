import hashlib
import json
from time import struct_time, mktime, time
from datetime import datetime, timedelta, UTC

from redis import Redis
from rq import Queue, get_current_job
import feedparser
feedparser.USER_AGENT = "Stroma News RSS Reader Bot"

from settings import log, QUEUE_NAME_FETCH, QUEUE_NAME_POST
from database.models import Feed, FeedFetch, Article
from media.meta import get_article_meta
from feeds.user import build_user_feed
from utils.filesystem import upload_user_feed_to_s3
from postbot.post import post_article


LATEST_DATE   = datetime.today() + timedelta(days=2)
EARLIEST_DATE = datetime.today() - timedelta(days=3)
ABSOLUTE_EARLIEST_DATE = EARLIEST_DATE
FEED_ERROR_THRESHOLD = 4

def fetch_feed_task(feed_id):

    try:
        feed = Feed.get(Feed.id==feed_id, Feed.active==True)
    except Feed.DoesNotExist:
        log.info(f"active feed {feed_id} not found")
        return None, None

    deactivate_feed_tokens = [":RecentChanges","/index.php?title=","bigcartel.com","buzzsprout.com"]
    if any(t in feed.uri for t in deactivate_feed_tokens):
        log.info(f"setting feed {feed.id} inactive because its uri looks undesirable")
        feed.state_change_reason = "undesirable feed: misc"
        feed.active = False
        feed.save()
        return None, None

    recent_fetches = list(FeedFetch.select().where(FeedFetch.feed==feed).order_by(FeedFetch.timestamp.desc()).limit(FEED_ERROR_THRESHOLD-1))
    last_fetch = recent_fetches[0] if recent_fetches else None

    fetch = FeedFetch(feed=feed)

    kwargs = {}

    # send the saved etag or modified field from the last fetch of this feed
    if last_fetch and last_fetch.etag:
        kwargs["etag"] = last_fetch.etag
        fetch.etag_sent = last_fetch.etag
    elif last_fetch and last_fetch.modified:
        kwargs["modified"] = last_fetch.modified
        fetch.modified_sent = last_fetch.modified

    try:
        t1 = time()
        fp = feedparser.parse(feed.uri, **kwargs)
        t2 = time()
        http_duration = t2 - t1
    except Exception as e:
        fetch.exception = f"{e.__class__.__name__} - {e}"
        log.error(fetch.exception)
        fp = None
        http_duration = None

    try:
        if fp:
            fetch.http_content_type = fp.http_content_type
    except Exception as e:
        log.warning(f"content-type missing from feed: {e}")

    bozo_exception = getattr(fp, "bozo_exception", None)
    if isinstance(bozo_exception, Exception):
        fetch.bozo_exception = f"{bozo_exception.__class__.__name__} - {bozo_exception}"
        if not "but parsed as" in fetch.bozo_exception and not "NonXMLContentType" in fetch.bozo_exception:
            log.warning(f"bozo exception for {feed.uri}: {fetch.bozo_exception}")


    # signal the following async job to skip itself. it's already been queued at this point.
    bozo_exception = fetch.bozo_exception or ""
    if fp is None or getattr(fp, "status", 999) >= 400 \
            or "SAXParseException" in bozo_exception \
            or "URLError" in bozo_exception:
        job = get_current_job()
        job.meta["skip"] = True
        job.save_meta()

    if not fp:
        fetch.http_duration = http_duration
        fetch.save()
        return fetch, fp

    # update feed database record if there are new values of certain fields
    for f in ["title","subtitle","image_url"]:
        model_value = getattr(feed, f, None)
        fetched_value = getattr(fp.feed, f, None)

        if fetched_value and fetched_value != model_value:
            setattr(feed, f, fetched_value)

    try:
        link_href = None
        for link in getattr(fp.feed, "links", []):
            if link["rel"] == "alternate" and link["type"] == "text/html":
                link_href = link["href"]
                break
        if link_href and link_href != feed.site_href:
            feed.site_href = link_href
    except Exception as e:
        log.warning(f"Couldn't update site_href: {e.__class__.__name__} - {e}")

    if feed.is_dirty():
        comments_feed_title_tokens = ["comments on:","comentarios en:","commentaires sur","reacties op:"]
        if feed.title and any(feed.title.lower().startswith(t) for t in comments_feed_title_tokens):
            feed.state_change_reason = "undesirable feed: comments"
            feed.active = False

        filter_str = (feed.title or "") + (feed.subtitle or "")
        tokens = ["18+","nsfw","xxx","porn","hentai","erotic","sexy"]
        if any(t in filter_str.lower() for t in tokens):
            feed.state_change_reason = "undesirable feed: inappropriate"
            feed.active = False

        feed.save()

    for field in ["etag","modified","modified_parsed","href","updated","updated_parsed","version","status"]:
        if hasattr(fp, field):
            val = getattr(fp, field)

            if isinstance(val, struct_time):
                val = datetime.fromtimestamp(mktime(val))

            setattr(fetch, field, val)

    fetch.http_duration = http_duration
    fetch.save()

    recent_fetches.append(fetch)

    server_error_strings = ["URLError","RemoteDisconnected","JobTimeoutException","IncompleteRead"]
    def error_fetch(f):
        exception_text = (f.exception or "") + (f.bozo_exception or "")
        status = f.status or 0
        return status >= 400 or any(s in exception_text for s in server_error_strings)

    if len(recent_fetches) >= FEED_ERROR_THRESHOLD and all(error_fetch(f) for f in recent_fetches):
        log.warning(f"setting feed {feed.id} inactive because last {len(recent_fetches)} fetches resulted in an http error status code")
        feed.active = False
        feed.state_change_reason = "too many recent http errors"
        feed.save()
        return None, None

    return fetch, fp


def save_articles_task(rebuild_for_user=None):

    r = Redis()
    queue_fetch = Queue(QUEUE_NAME_FETCH, connection=r)
    queue_post = Queue(QUEUE_NAME_POST, connection=r)

    current_job = get_current_job()
    job = queue_fetch.fetch_job(current_job.dependency.id)
    
    if job.meta.get("skip"):
        return

    try:
        fetch, fp = job.result
        if not fetch and not fp:
            return
    except:
        log.error(f"error fetching result for job {job.id} in save_articles_task")
        raise

    articles = save_articles(fetch, fp)
    articles = [a for a in articles if a.link != "(none)"]

    if not articles:
        return

    post_article_jobs = []

    for article in articles:

        terms = [line.strip("\r\n") for line in open("ignore-terms.txt")]
        if any(t in (article.title or "").lower()+(article.summary or "").lower()+article.link for t in terms):
            continue

        get_article_meta_job = queue_fetch.enqueue(get_article_meta, article.id, result_ttl=14400)
        post_article_job = queue_post.enqueue(post_article, article.id, depends_on=get_article_meta_job, result_ttl=14400)
        post_article_jobs.append(post_article_job)

    if rebuild_for_user:
        build_user_feed_job = queue_fetch.enqueue(build_user_feed, rebuild_for_user, depends_on=post_article_jobs)
        upload_job = queue_fetch.enqueue(upload_user_feed_to_s3, rebuild_for_user, depends_on=build_user_feed_job)

    return len(articles)
    

def save_articles(fetch, fp):

    saved_articles = []
    for n,entry in enumerate(fp.entries):

        # convert these fields to datetime objects
        for field in ["published_parsed","updated_parsed"]:
            try:
                setattr(entry, field, datetime.fromtimestamp(mktime(getattr(entry, field))))
            except:
                setattr(entry, field, None)

        # save article if this feed has never been fetched before, or if it falls in the date window
        if (entry.published_parsed and entry.published_parsed < EARLIEST_DATE) \
            or (entry.updated_parsed and entry.updated_parsed < EARLIEST_DATE) \
            or (entry.published_parsed and entry.published_parsed > LATEST_DATE) \
            or (entry.updated_parsed and entry.updated_parsed > LATEST_DATE):
            continue

        if not hasattr(entry, "id"):
            try:
                entry.id = hashlib.sha1(entry.link.encode('utf-8')).hexdigest()
            except AttributeError:
                entry.id = hashlib.sha1(str(entry).encode('utf-8')).hexdigest()
        
        existing_articles = Article.select().where(Article.entry_id==entry.id).count()
        if existing_articles > 0:
            continue

        if getattr(entry, "link", None):
            existing_articles = Article.select().where(Article.link==entry.link).count()
            if existing_articles > 0:
                continue

        title = getattr(entry, "title", "") or ""
        if len(title) >= 30:
            existing_article = Article.select().where(Article.title==title, Article.published_parsed >= datetime.now(UTC) - timedelta(hours=72)).first()
            if existing_article:
                continue

        article = Article(feed_fetch=fetch, entry_id=entry.id)

        for field in ["title","summary","author","link","updated","updated_parsed","published","published_parsed"]:
            setattr(article, field, getattr(entry, field, None))

        try:
            article.tags = json.dumps([t['term'] for t in entry.tags[:16]])
        except:
            pass

        if not article.link:
            log.info(f"article with entry {article.entry_id} has no link")
            article.link = "(none)"

        # note - race condition possible if articles were inserted after the
        # Article.select().where(Article.entry_id==entry.id) check above,
        # if the same feed under 2 different uris are being fetched at once
        # from two different workers.
        article.save()
        saved_articles.append(article)

    fetch.articles_saved = len(saved_articles)
    fetch.save()
    return saved_articles
