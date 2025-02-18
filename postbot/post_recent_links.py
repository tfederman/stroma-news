from datetime import datetime, timedelta, UTC

from redis import Redis
from rq import Queue
import peewee

from settings import log, QUEUE_NAME_POST
from database.models import Article, ArticlePost, FeedFetch, ArticleMeta
from postbot.post import post_article


def post_recent_links():
    """This is probably obsolete now that post_article is queued as part of the fetch
    task pipeline. At a minimum, this query may no longer be up to date."""
    q = Queue(QUEUE_NAME_POST, connection=Redis())

    articles = Article.select() \
        .join(FeedFetch) \
        .join(ArticleMeta, on=(Article.id==ArticleMeta.article_id)) \
        .join(ArticlePost, peewee.JOIN.LEFT_OUTER, on=(ArticlePost.article_id==Article.id)) \
        .where(ArticlePost.id==None) \
        .where(Article.published_parsed >= datetime.now(UTC) - timedelta(hours=72)) \
        .where(FeedFetch.timestamp >= datetime.now(UTC) - timedelta(hours=24)) \
        .order_by(peewee.fn.random())

    # keep within hourly rate limit (5000 points/hour @ 3 points/create)
    articles = articles[:800]

    for n,article in enumerate(articles):
        log.info(f"{n+1}/{len(articles)} - {article.id} - {article.title}")
        job = q.enqueue(post_article, article.id, result_ttl=14400)
