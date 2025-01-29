import hashlib
import json
from time import struct_time, mktime, time
from datetime import datetime, timedelta

import peewee
import feedparser
feedparser.USER_AGENT = "Stroma News RSS Reader Bot"

from database import db
from database.models import Feed, Fetch, Article

EARLIEST_DATE = datetime.today() - timedelta(days=30)
LATEST_DATE   = datetime.today() + timedelta(days=2)


def fetch_feed(feed, last_fetch):

    fetch = Fetch(feed=feed)

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


def save_articles(fetch, fp):

    saved_articles = []
    for entry in fp.entries:

        for field in ["published_parsed","updated_parsed"]:
            try:
                setattr(entry, field, datetime.fromtimestamp(mktime(getattr(entry, field))))
            except:
                setattr(entry, field, None)

        if (entry.published_parsed and entry.published_parsed < EARLIEST_DATE) \
            or (entry.updated_parsed and entry.updated_parsed < EARLIEST_DATE) \
            or (entry.published_parsed and entry.published_parsed > LATEST_DATE) \
            or (entry.updated_parsed and entry.updated_parsed > LATEST_DATE):
            # to do - log to file
            # to do - allow articles earlier than window if it's the first time fetching the feed
            continue

        if not hasattr(entry, "id"):
            try:
                entry.id = hashlib.sha1(entry.link.encode('utf-8')).hexdigest()
            except AttributeError:
                entry.id = hashlib.sha1(str(entry).encode('utf-8')).hexdigest()
        
        articles = Article.select().where(Article.entry_id==entry.id)
        if len(articles) > 0:
            continue

        article = Article(fetch=fetch, entry_id=entry.id)

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


def should_fetch_feed(feed, days=7):
    try:
        last_fetch = Fetch.select().where(Fetch.feed==feed).order_by(Fetch.timestamp.desc()).limit(1)[0]
    except IndexError:
        return True

    # check age of the most recent fetch of this feed
    if last_fetch.updated_parsed and datetime.today() - last_fetch.updated_parsed > timedelta(days=days):
        return False

    try:
        last_article = Article.select().where(Article.fetch==last_fetch).order_by(Article.published_parsed.desc()).limit(1)[0]

        # check age of the most recent article from this feed
        if last_article.published_parsed and datetime.today() - last_article.published_parsed > timedelta(days=days):
            return False

    except IndexError:
        return True

    return True


def get_last_fetch(feed):
    try:
        return Fetch.select().where(Fetch.feed==feed).order_by(Fetch.timestamp.desc()).limit(1)[0]
    except IndexError as e:
        return None


if __name__=='__main__':

    if db.is_closed():
        db.connect()

    feeds = list(Feed.select().order_by(peewee.fn.Random()))

    # specific feed
    # feeds = list(Feed.select().where(Feed.uri=="..."))

    # feeds that have never been fetched
    # feeds = list(Feed.select().join(Fetch, peewee.JOIN.LEFT_OUTER, on=(Feed.id == Fetch.feed_id)).where(Fetch.id==None))

    feeds = [feed for feed in feeds if should_fetch_feed(feed, days=2)]

    for n,feed in enumerate(feeds):
        print(f"{n:04}/{len(feeds):04} {feed.uri}")

        last_fetch = get_last_fetch(feed)

        fetch, fp = fetch_feed(feed, last_fetch)

        if not fp:
            continue

        saved_articles = save_articles(fetch, fp)

        if saved_articles:
            print(f"status {getattr(fp, 'status', '???')}, {len(saved_articles)} articles saved")
