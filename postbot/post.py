import time
import traceback

from bsky import session
from settings import log
from media.card import get_post
from database.models import Article, ArticlePost


def post_article(article_id):
    try:
        article = Article.get(Article.id==article_id)
        post, remote_metadata_lookup = get_post(session, article)
        response = session.create_record(post)
        uri = response.uri
        post_id = response.uri.split("/")[-1]
        exception = None
    except Exception as e:
        exception = f"{e.__class__.__name__} - {e}\n{traceback.format_exc()}"
        uri = None
        post_id = None
        remote_metadata_lookup = False
        log.error(f"error making post: {e.__class__.__name__} - {e}")

    article_post = ArticlePost(uri=uri, post_id=post_id, article=article, exception=exception, remote_metadata_lookup=remote_metadata_lookup)
    article_post.save()

    # sleep longer if a call was made to an external service (avoids http 429s)
    if remote_metadata_lookup:
        time.sleep(3)
    else:
        time.sleep(1)

    return article_post.id
