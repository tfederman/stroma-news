from datetime import datetime, timedelta, UTC

from redis import Redis
from rq import Queue

from settings import log
from database.models import Feed, FeedFetch, Article
from feeds.tasks import *


def get_feeds_to_fetch(recent_fetch_hours=6, recent_fetch_content_days=30):

    now = datetime.now(UTC)

    # feeds to fetch = all_feeds - feeds fetched in last n hours - feeds without article published in last n days - feeds not updated in last n days
    all_feeds = set(Feed.select().where(Feed.active==True))
    feeds_recently_fetched = set(Feed.select().join(FeedFetch).where(now - FeedFetch.timestamp < timedelta(hours=recent_fetch_hours)))
    feeds_without_recent_published_article = set(Feed.select().join(FeedFetch).join(Article).where(now - Article.published_parsed > timedelta(days=recent_fetch_content_days)))
    feeds_without_recent_update = set(Feed.select().join(FeedFetch).where(now - FeedFetch.updated_parsed > timedelta(days=recent_fetch_content_days)))

    feeds_to_fetch = all_feeds \
                        - feeds_recently_fetched \
                        - feeds_without_recent_published_article \
                        - feeds_without_recent_update

    return list(feeds_to_fetch)


if __name__=='__main__':

    q = Queue(connection=Redis())

    feeds_to_fetch = get_feeds_to_fetch()
    #print(len(feeds_to_fetch))
    #exit(0)

    for n,feed in enumerate(feeds_to_fetch):
        log.info(f"{n+1:04}/{len(feeds_to_fetch):04} {feed.uri}")
        job_fetch = q.enqueue(fetch_feed_task, feed, result_ttl=86400)
        job_save  = q.enqueue(save_articles_task, depends_on=job_fetch, result_ttl=86400)
