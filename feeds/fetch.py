import hashlib
import json
from time import struct_time, mktime, time
from datetime import datetime, timedelta

import feedparser
feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

from database import *

EARLIEST_DATE = datetime.today() - timedelta(days=30) # datetime(2025, 1, 1)
LATEST_DATE   = datetime.today() + timedelta(days=2)

def fetch_and_save_feed(feed):
    try:
        last_fetch = Fetch.select().where(Fetch.feed==feed).order_by(Fetch.timestamp.desc()).limit(1)[0]
    except IndexError as e:
        last_fetch = None

    fetch = Fetch(feed=feed)

    kwargs = {}
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
        print(fetch.exception)
        fp = None
        http_duration = None

    try:
        if fp:
            img = fp.feed.image
            with open("feed-images.txt", "a") as f:
                f.write(f"{feed.id}\t{feed.uri}\t{img}\n")
    except Exception as e:
        pass


    try:
        if fp.feed.title != feed.title:
            feed.title = fp.feed.title
            feed.save()
    except Exception as e:
        pass

    try:
        if fp.feed.subtitle != feed.subtitle:
            feed.subtitle = fp.feed.subtitle
            feed.save()
    except Exception as e:
        pass

    try:
        link_href = None
        for link in fp.feed.links:
            if link["rel"] == "alternate" and link["type"] == "text/html":
                link_href = link["href"]
                break
        if link_href and link_href != feed.site_href:
            feed.site_href = link_href
            feed.save()
    except Exception as e:
        pass

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

    articles_saved = 0
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
            #print(f"skip {datetime.fromtimestamp(mktime(entry.updated_parsed))}")
            # to do - log to file
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
        articles_saved += 1

    return articles_saved


def should_fetch_feed(feed, days=7):
    try:
        last_fetch = Fetch.select().where(Fetch.feed==feed).order_by(Fetch.timestamp.desc()).limit(1)[0]
    except IndexError:
        return True

    if last_fetch.updated_parsed and datetime.today() - last_fetch.updated_parsed > timedelta(days=days):
        #print(f"fetch too old: {last_fetch.updated_parsed}")
        return False

    try:
        last_article = Article.select().where(Article.fetch==last_fetch).order_by(Article.published_parsed.desc()).limit(1)[0]
        #if not last_article.published_parsed:
        #    continue
        # to do - 20
        if last_article.published_parsed and datetime.today() - last_article.published_parsed > timedelta(days=days):
            #print(f"article too old: {last_article.published_parsed}")
            return False
    except IndexError:
        return True

    return True


if __name__=='__main__':

    if db.is_closed():
        db.connect()

    feeds = list(Feed.select().order_by(peewee.fn.Random()))
    #feeds = list(Feed.select().where(Feed.uri=="..."))

    # feeds that have never been fetched
    #feeds = list(Feed.select().join(Fetch, peewee.JOIN.LEFT_OUTER, on=(Feed.id == Fetch.feed_id)).where(Fetch.id==None))

    feeds = [feed for feed in feeds if should_fetch_feed(feed, days=4)]

    for n,feed in enumerate(feeds):
        print(f"{n:04}/{len(feeds):04} {feed.uri}")

        fetch, fp = fetch_and_save_feed(feed)

        if not fp:
            continue

        articles_saved = save_articles(fetch, fp)

        try:
            print(f"status {fp.status}, {articles_saved} articles saved")
        except:
            print(f"no fp.status, {articles_saved} articles saved")
