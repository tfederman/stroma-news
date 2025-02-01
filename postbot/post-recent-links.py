import time
import traceback
from datetime import datetime, timedelta, UTC

import peewee

from bsky import session
from media.card import get_post
from database import db
from database.models import Article, ArticlePost, FeedFetch, ArticleMeta


def post_article(session, article):
    try:
        post, cardy_lookup = get_post(session, article)

        response = session.create_record(post)
        uri = response.uri
        post_id = response.uri.split("/")[-1]
        exception = None
    except Exception as e:
        exception = f"{e.__class__.__name__} - {e}\n{traceback.format_exc()}"
        uri = None
        post_id = None
        cardy_lookup = False

    article_post = ArticlePost(uri=uri, post_id=post_id, article=article, exception=exception)
    article_post.save()
    return article_post, cardy_lookup


if __name__ == "__main__":

    articles = Article.select() \
        .join(FeedFetch) \
        .join(ArticleMeta, on=(Article.id==ArticleMeta.article_id)) \
        .join(ArticlePost, peewee.JOIN.LEFT_OUTER, on=(ArticlePost.article_id==Article.id)) \
        .where(ArticlePost.id==None) \
        .where(FeedFetch.timestamp >= datetime.now(UTC) - timedelta(hours=24)) \
        .order_by(peewee.fn.random())

    # keep within hourly rate limit (5000 points/hour @ 3 points/create)
    articles = articles[:1600]

    for n,article in enumerate(articles):
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {n+1}/{len(articles)} - {article.id} - {article.title}")

        article_post, cardy_lookup = post_article(session, article)

        if article_post.exception:
            print(f"+++ EXCEPTION {article_post.id} -", article_post.exception)

        if cardy_lookup:
            # a call was made to an external service, slow down to avoid rate limiting
            time.sleep(3)
        else:
            time.sleep(1)
