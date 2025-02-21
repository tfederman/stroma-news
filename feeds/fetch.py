from datetime import datetime, timedelta

from peewee import fn, JOIN
from redis import Redis
from rq import Queue

from settings import log, QUEUE_NAME_FETCH, TIMEZONE
from database.models import Feed, FeedFetch, Article
from feeds.tasks import fetch_feed_task, save_articles_task


def get_feeds_to_fetch():

    now = datetime.now(TIMEZONE)

    # get all active feeds annotated with last fetch time and most recent article time
    feeds = Feed.select(Feed.id, Feed.uri, fn.max(FeedFetch.timestamp).alias("max_ts"), fn.max(Article.published_parsed).alias("max_pp")).join(FeedFetch).join(Article, JOIN.LEFT_OUTER).where(Feed.active==True).group_by(Feed).namedtuples()

    return_feeds = []

    for f in feeds:

        if not f.max_pp:
            continue

        last_fetched = now - f.max_ts
        last_article = now - f.max_pp

        # include this one if very recently published but not fetched very recently
        if last_fetched > timedelta(hours=8) and last_article < timedelta(days=2):
            return_feeds.append(f)

        # include this one if less recently published but not fetched less recently
        elif last_fetched > timedelta(hours=48) and last_article < timedelta(days=7):
            return_feeds.append(f)

        # include this one if less recently published but not fetched less recently
        elif last_fetched > timedelta(hours=96) and last_article < timedelta(days=14):
            return_feeds.append(f)

        # include this one if less recently published but not fetched less recently
        elif last_fetched > timedelta(hours=168) and last_article < timedelta(days=30):
            return_feeds.append(f)

        # include this one if less recently published but not fetched less recently
        elif last_fetched > timedelta(hours=336) and last_article < timedelta(days=90):
            return_feeds.append(f)

    # add feeds that have never been fetched
    return_feeds += list(Feed.select().join(FeedFetch, JOIN.LEFT_OUTER).where(FeedFetch.id==None, Feed.active==True))

    # to do - add (some) feeds that have been fetched but have no articles

    return return_feeds


def enqueue_fetch_tasks():

    q = Queue(QUEUE_NAME_FETCH, connection=Redis())

    feeds_to_fetch = get_feeds_to_fetch()
    total_count = len(feeds_to_fetch)
    feeds_to_fetch = feeds_to_fetch[:200]

    for n,feed in enumerate(feeds_to_fetch):
        job_fetch = q.enqueue(fetch_feed_task, feed.id, result_ttl=14400)
        job_save  = q.enqueue(save_articles_task, depends_on=job_fetch, result_ttl=14400)

    log.info(f"{len(feeds_to_fetch)} feeds queued out of {total_count} total feeds")
