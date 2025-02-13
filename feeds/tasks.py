import hashlib
import json
from time import struct_time, mktime, time
from datetime import datetime, timedelta

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
EARLIEST_DATE = datetime.today() - timedelta(days=30)
ABSOLUTE_EARLIEST_DATE = datetime(2024, 1, 1)

# to do - check last [n] fetches here, if all are errors, set feed inactive
def fetch_feed_task(feed_id):

    feed = Feed.get(feed_id)
    last_fetch = get_last_fetch(feed)

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
        log.error(f"bozo exception for {feed.uri}: {fetch.bozo_exception}")


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
        return fetch, fp, last_fetch

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
        feed.save()

    for field in ["etag","modified","modified_parsed","href","updated","updated_parsed","version","status"]:
        if hasattr(fp, field):
            val = getattr(fp, field)

            if isinstance(val, struct_time):
                val = datetime.fromtimestamp(mktime(val))

            setattr(fetch, field, val)

    fetch.http_duration = http_duration
    fetch.save()
    return fetch, fp, last_fetch


def save_articles_task(rebuild_for_user=None):

    r = Redis()
    queue_fetch = Queue(QUEUE_NAME_FETCH, connection=r)
    queue_post = Queue(QUEUE_NAME_POST, connection=r)

    current_job = get_current_job()
    job = queue_fetch.fetch_job(current_job.dependency.id)
    
    if job.meta.get("skip"):
        return

    try:
        fetch, fp, last_fetch = job.result
    except:
        log.error(f"error fetching result for job {job.id} in save_articles_task")
        raise

    articles = save_articles(fetch, fp, last_fetch)
    articles = [a for a in articles if a.link != "(none)"]

    if not articles:
        return

    post_article_jobs = []

    for article in articles:
        get_article_meta_job = queue_fetch.enqueue(get_article_meta, (article.id,), result_ttl=28800)
        post_article_job = queue_post.enqueue(post_article, (article.id,), depends_on=get_article_meta_job, result_ttl=28800)
        post_article_jobs.append(post_article_job)

    if rebuild_for_user:
        build_user_feed_job = queue_fetch.enqueue(build_user_feed, rebuild_for_user, depends_on=post_article_jobs)
        upload_job = queue_fetch.enqueue(upload_user_feed_to_s3, rebuild_for_user, depends_on=build_user_feed_job)

    return len(articles)
    

def save_articles(fetch, fp, last_fetch):

    saved_articles = []
    for n,entry in enumerate(fp.entries):

        # convert these fields to datetime objects
        for field in ["published_parsed","updated_parsed"]:
            try:
                setattr(entry, field, datetime.fromtimestamp(mktime(getattr(entry, field))))
            except:
                setattr(entry, field, None)

        # save article if this feed has never been fetched before, or if it falls in the date window
        if last_fetch:
            if (entry.published_parsed and entry.published_parsed < EARLIEST_DATE) \
                or (entry.updated_parsed and entry.updated_parsed < EARLIEST_DATE) \
                or (entry.published_parsed and entry.published_parsed > LATEST_DATE) \
                or (entry.updated_parsed and entry.updated_parsed > LATEST_DATE):
                log.warning(f"skipping article: {entry.updated_parsed}, {entry.published_parsed} ({EARLIEST_DATE}, {LATEST_DATE})")
                continue


        # limit feeds with very long history
        if entry.published_parsed and entry.published_parsed < ABSOLUTE_EARLIEST_DATE:
            continue

        # limit feeds with very long history
        if n >= 100:
            continue

        if not hasattr(entry, "id"):
            try:
                entry.id = hashlib.sha1(entry.link.encode('utf-8')).hexdigest()
            except AttributeError:
                entry.id = hashlib.sha1(str(entry).encode('utf-8')).hexdigest()
        
        articles = Article.select().where(Article.entry_id==entry.id)
        if len(articles) > 0:
            continue

        article = Article(feed_fetch=fetch, entry_id=entry.id)

        for field in ["title","summary","author","link","updated","updated_parsed","published","published_parsed"]:
            setattr(article, field, getattr(entry, field, None))

        try:
            article.tags = json.dumps([t['term'] for t in entry.tags[:16]])
        except:
            pass

        if not article.link:
            article.link = "(none)"

        article.save()
        saved_articles.append(article)

    fetch.articles_saved = len(saved_articles)
    fetch.save()
    return saved_articles


def get_last_fetch(feed):
    try:
        return FeedFetch.select().where(FeedFetch.feed==feed).order_by(FeedFetch.timestamp.desc()).limit(1)[0]
    except IndexError as e:
        return None
