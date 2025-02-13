from datetime import datetime, timedelta

from peewee import fn, JOIN
from redis import Redis
from rq import Queue

from settings import log, QUEUE_NAME_FETCH, TIMEZONE
from database.models import Feed, FeedFetch, Article
from feeds.tasks import fetch_feed_task, save_articles_task


def get_feeds_to_fetch(recent_fetch_hours=6, recent_fetch_content_days=4):

    now = datetime.now(TIMEZONE)

    # get all active feeds annotated with last fetch time and most recent article time
    feeds = Feed.select(Feed.id, Feed.uri, fn.max(FeedFetch.timestamp).alias("max_ts"), fn.max(Article.published_parsed).alias("max_pp")).join(FeedFetch).join(Article, JOIN.LEFT_OUTER).where(Feed.active==True).group_by(Feed).namedtuples()

    # subtract feeds that were fetched recently
    feeds = [f for f in feeds if now-f.max_ts > timedelta(hours=recent_fetch_hours)]

    # subtract feeds that have not had an article published recently
    feeds = [f for f in feeds if (f.max_pp is not None) and (now-f.max_pp > timedelta(days=recent_fetch_content_days))]

    # add feeds that have never been fetched
    feeds += list(Feed.select().join(FeedFetch, JOIN.LEFT_OUTER).where(FeedFetch.id==None, Feed.active==True))

    # to do - subtract feeds that have consistently errored?

    return feeds


if __name__=='__main__':

    q = Queue(QUEUE_NAME_FETCH, connection=Redis())

    feeds_to_fetch = get_feeds_to_fetch()
    feeds_to_fetch = feeds_to_fetch[:400]
    #print(len(feeds_to_fetch))
    #exit(0)

    for n,feed in enumerate(feeds_to_fetch):
        log.info(f"{n+1:04}/{len(feeds_to_fetch):04} {feed.uri}")
        job_fetch = q.enqueue(fetch_feed_task, feed.id, result_ttl=28800)
        job_save  = q.enqueue(save_articles_task, depends_on=job_fetch, result_ttl=28800)
