import random
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
    feeds = (
        Feed.select(
            Feed.id,
            Feed.uri,
            fn.max(FeedFetch.timestamp).alias("max_ts"),
            fn.max(Article.published_parsed).alias("max_pp"),
            fn.max(FeedFetch.status).alias("max_status"),
            fn.count(FeedFetch.id).alias("count_fetches"),
            fn.sum(FeedFetch.articles_saved).alias("sum_articles_saved"),
        )
        .join(FeedFetch)
        .join(Article, JOIN.LEFT_OUTER)
        .where(Feed.active == True)
        .group_by(Feed)
        .namedtuples()
    )

    return_feeds = []

    for f in feeds:

        last_fetched = now - f.max_ts

        if not f.max_pp:
            if last_fetched > timedelta(days=7) and f.max_status == 200 and random.random() <= 0.1:
                return_feeds.append(f)
            continue

        last_article = now - f.max_pp

        # include this one if very recently published but not fetched very recently
        if last_fetched > timedelta(hours=24) and last_article < timedelta(days=2):
            return_feeds.append(f)

        # include this one if less recently published but not fetched less recently
        elif last_fetched > timedelta(hours=36) and last_article < timedelta(days=14):
            return_feeds.append(f)

        # include this one if less recently published but not fetched less recently
        elif last_fetched > timedelta(hours=72) and last_article < timedelta(days=21):
            return_feeds.append(f)

        # include this one if less recently published but not fetched less recently
        elif last_fetched > timedelta(hours=80) and last_article < timedelta(days=90):
            return_feeds.append(f)

        # include this one if less recently published but not fetched less recently
        elif last_fetched > timedelta(hours=96) and last_article < timedelta(days=180):
            return_feeds.append(f)

    # add feeds that have never been fetched
    return_feeds += list(
        Feed.select()
        .join(FeedFetch, JOIN.LEFT_OUTER)
        .where(FeedFetch.id == None, Feed.active == True)
    )

    return return_feeds


def enqueue_fetch_tasks():

    q = Queue(QUEUE_NAME_FETCH, connection=Redis())

    feeds_to_fetch = get_feeds_to_fetch()
    total_count = len(feeds_to_fetch)
    feeds_to_fetch = feeds_to_fetch[:180]

    for n, feed in enumerate(feeds_to_fetch):
        job_fetch = q.enqueue(fetch_feed_task, feed.id, ttl=3600, result_ttl=3600)
        job_save = q.enqueue(save_articles_task, depends_on=job_fetch, ttl=3600, result_ttl=3600)

    log.info(f"{len(feeds_to_fetch)} feeds queued out of {total_count} total feeds")
