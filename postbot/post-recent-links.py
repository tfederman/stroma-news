import time
from datetime import datetime, timedelta

from bsky.client import Session
from media.card import get_post
from database import db
from database.models import Article, ArticlePost, Fetch


def post_article(session, article):
    try:
        post = get_post(session, article.fetch.feed.title,
            article.title, article.link, article.summary,
            article.published_parsed, article.author)

        response = session.create_record(post)
        uri = response.uri
        post_id = response.uri.split("/")[-1]
        exception = None
    except Exception as e:
        exception = f"{e.__class__.__name__} - {e}"
        uri = None
        post_id = None

    article_post = ArticlePost(uri=uri, post_id=post_id, article=article, exception=exception)
    article_post.save()
    return article_post


if __name__ == "__main__":

    db.connect()
    session = Session()

    articles = Article.select() \
        .join(Fetch) \
        .join(ArticlePost, peewee.JOIN.LEFT_OUTER, on=(ArticlePost.article_id==Article.id)) \
        .where(ArticlePost.id==None) \
        .where(Fetch.timestamp >= datetime.now() - timedelta(hours=4))

    # keep within hourly rate limit (5000 points/hour @ 3 points/create)
    articles = articles[:1500]

    for n,article in enumerate(articles):
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {n+1}/{len(articles)} - {article.title}")
        article_post = post_article(session, article)
        if article_post.exception:
            print(f"+++ EXCEPTION {article_post.id} -", article_post.exception)
        time.sleep(1)
