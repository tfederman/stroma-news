import peewee

from bsky import session
from media.card import get_post
from database import db
from database.models import Article, ArticlePost

if __name__ == "__main__":

    #article = Article.select().where(Article.link=="https://www.theatlantic.com/culture/archive/2025/01/fka-twigs-eusexua-review/681490/?utm_source=feed").order_by(peewee.fn.random()).limit(1)[0]
    article = Article.select().order_by(peewee.fn.random()).limit(1)[0]

    try:
        post = get_post(session, article.feed_fetch.feed.title,
            article.title, article.link, article.summary,
            article.published_parsed, article.author)
        response = session.create_record(post)
        print(response)
        uri = response.uri
        post_id = response.uri.split("/")[-1]
        exception = None
    except Exception as e:
        exception = f"{e.__class__.__name__} - {e}"
        uri = None
        post_id = None

    article_post = ArticlePost(uri=uri, post_id=post_id, article=article, exception=exception)
    article_post.save()
