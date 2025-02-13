import time
import traceback
from datetime import datetime, timedelta

from bsky import session
from settings import log, TIMEZONE
from media.card import get_post
from database.models import Article, ArticlePost


def post_article(article_id):

    # to do - if there are [n] 500 errors in the last few minutes, pause or stop worker, reschedule, etc

    try:
        article = Article.get(Article.id==article_id)

        if len(article.articlepost_set) > 0:
            log.warning(f"tried to post article ({article_id}) that already has an article_post")
            return article.articlepost_set[0].id

        TEMPORARY_EARLIEST_DATE = datetime.now(TIMEZONE) - timedelta(days=10)
        if article.published_parsed and article.published_parsed <= TEMPORARY_EARLIEST_DATE:
            log.warning(f"article {article.id} skipped in post_article because it's too old: {article.published_parsed}")
            return

        post, remote_metadata_lookup = get_post(session, article)
        response = session.create_post(post)
        uri = response.uri
        post_id = response.uri.split("/")[-1]
        exception = None
    except Exception as e:
        exception = f"{e.__class__.__name__} - {e}\n{traceback.format_exc()}"
        uri = None
        post_id = None
        remote_metadata_lookup = "cardy_lookup: True" in str(e)
        log.error(f"error making post: {e.__class__.__name__} - {e}")

    article_post = ArticlePost(uri=uri, post_id=post_id, article=article, exception=exception, remote_metadata_lookup=remote_metadata_lookup)
    article_post.save()

    # sleep longer if a call was made to an external service (avoids http 429s)
    if remote_metadata_lookup:
        time.sleep(3)
    else:
        time.sleep(1)

    return article_post.id
