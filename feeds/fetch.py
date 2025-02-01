import hashlib
import json
from time import struct_time, mktime, time
from datetime import datetime, timedelta, UTC

import peewee
import feedparser
feedparser.USER_AGENT = "Stroma News RSS Reader Bot"

from database import db
from database.models import Feed, FeedFetch, Article
from media.meta import get_article_meta

LATEST_DATE   = datetime.today() + timedelta(days=2)
EARLIEST_DATE = datetime.today() - timedelta(days=30)
ABSOLUTE_EARLIEST_DATE = datetime(2024, 1, 1)


def fetch_feed(feed, last_fetch):

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
        fetch.exception = f"{type(e)} - {str(e)}"
        # log to database
        print(fetch.exception)
        fp = None
        http_duration = None

    try:
        if fp:
            fetch.http_content_type = fp.http_content_type
    except Exception as e:
        print(f"content-type error: {e}")

    # update feed database record if there are new values of certain fields
    for f in ["title","subtitle","image_url"]:
        model_value = getattr(feed, f, None)
        fetched_value = getattr(fp.feed, f, None)

        if fetched_value and fetched_value != model_value:
            setattr(feed, f, fetched_value)

    try:
        link_href = None
        for link in fp.feed.links:
            if link["rel"] == "alternate" and link["type"] == "text/html":
                link_href = link["href"]
                break
        if link_href and link_href != feed.site_href:
            feed.site_href = link_href
    except Exception as e:
        pass

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
    return fetch, fp


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
                # to do - log somewhere?
                continue


        # limit feeds with very long history
        if entry.published_parsed and entry.published_parsed < ABSOLUTE_EARLIEST_DATE:
            continue

        # limit feeds with very long history
        if n >= 60:
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

    return saved_articles


def get_last_fetch(feed):
    try:
        return FeedFetch.select().where(FeedFetch.feed==feed).order_by(FeedFetch.timestamp.desc()).limit(1)[0]
    except IndexError as e:
        return None


def get_feeds_to_fetch(recent_fetch_hours=2, recent_fetch_content_days=4):

    now = datetime.now(UTC)

    # feeds to fetch = all_feeds - feeds fetched in last n hours - feeds without article published in last n days - feeds not updated in last n days
    all_feeds = set(Feed.select())
    feeds_recently_fetched = set(Feed.select().join(FeedFetch).where(now - FeedFetch.timestamp < timedelta(hours=recent_fetch_hours)))
    feeds_without_recent_published_article = set(Feed.select().join(FeedFetch).join(Article).where(now - Article.published_parsed > timedelta(days=recent_fetch_content_days)))
    feeds_without_recent_update = set(Feed.select().join(FeedFetch).where(now - FeedFetch.updated_parsed > timedelta(days=recent_fetch_content_days)))

    feeds_to_fetch = all_feeds \
                        - feeds_recently_fetched \
                        - feeds_without_recent_published_article \
                        - feeds_without_recent_update

    return list(feeds_to_fetch)


if __name__=='__main__':

    if db.is_closed():
        db.connect()

    # feeds = list(Feed.select().order_by(peewee.fn.Random()))

    # specific feed
    # feeds = list(Feed.select().where(Feed.uri=="..."))

    # feeds that have never been fetched
    # feeds = list(Feed.select().join(FeedFetch, peewee.JOIN.LEFT_OUTER, on=(Feed.id == FeedFetch.feed_id)).where(FeedFetch.id==None))

    feeds_to_fetch = get_feeds_to_fetch()
    feeds_to_fetch = feeds_to_fetch[:1000]
    #feeds_to_fetch = list(Feed.select().order_by(peewee.fn.Random()))[:10]

    for n,feed in enumerate(feeds_to_fetch):
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {n+1:04}/{len(feeds_to_fetch):04} {feed.uri}")

        last_fetch = get_last_fetch(feed)

        fetch, fp = fetch_feed(feed, last_fetch)

        if not fp:
            continue

        saved_articles = save_articles(fetch, fp, last_fetch)

        # based on date of most recent article, schedule the next fetch

        for article in saved_articles:
            get_article_meta(article)

        if saved_articles:
            print(f"status {getattr(fp, 'status', '???')}, {len(saved_articles)} articles saved")
