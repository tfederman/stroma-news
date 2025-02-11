from datetime import datetime, timedelta, UTC

from redis import Redis
from rq import Queue
import peewee

from bsky import session
from settings import log, QUEUE_NAME_POST
from database.models import Article, ArticlePost, FeedFetch, ArticleMeta
from postbot.post import post_article


if __name__ == "__main__":

    q = Queue(QUEUE_NAME_POST, connection=Redis())

    articles = Article.select() \
        .join(FeedFetch) \
        .join(ArticleMeta, on=(Article.id==ArticleMeta.article_id)) \
        .join(ArticlePost, peewee.JOIN.LEFT_OUTER, on=(ArticlePost.article_id==Article.id)) \
        .where(ArticlePost.id==None) \
        .where(Article.published_parsed >= datetime.now(UTC) - timedelta(hours=72)) \
        .where(FeedFetch.timestamp >= datetime.now(UTC) - timedelta(hours=24)) \
        .order_by(peewee.fn.random())

    #print(len(articles))
    #exit(0)

    # keep within hourly rate limit (5000 points/hour @ 3 points/create)
    articles = articles[:800]

    for n,article in enumerate(articles):
        log.info(f"{n+1}/{len(articles)} - {article.id} - {article.title}")
        job = q.enqueue(post_article, article.id, result_ttl=28800)
