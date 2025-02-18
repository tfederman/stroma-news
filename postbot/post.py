import time
import traceback
from datetime import datetime, timedelta

import redis

from bsky import session
from settings import log, TIMEZONE
from media.card import get_post
from database.models import Article, ArticlePost, ArticlePostRetry

MAX_SERVER_ERROR_COUNT = 5
SERVER_ERROR_COUNT_KEY = "server_error_count"

def create_retry(article, article_post=None, td=None):
    td = td or timedelta(minutes=10)
    retry_at = datetime.now(TIMEZONE) + td
    ArticlePostRetry.create(article=article, article_post=article_post, retry_at=retry_at)


def post_article(article_id):

    article = Article.get(Article.id==article_id)

    r = redis.Redis()
    server_error_count = int(r.get(SERVER_ERROR_COUNT_KEY) or 0)
    if server_error_count >= MAX_SERVER_ERROR_COUNT:
        log.warning(f"not posting article {article.id} because of recent 500 errors ({server_error_count})")
        create_retry(article)
        return

    try:

        if not article.feed_fetch.feed.active:
            log.warning(f"tried to post article ({article.id}) but its feed is now inactive")
            return

        if len(article.articlepost_set) > 0:
            # if exception, allow retry?
            log.warning(f"tried to post article ({article.id}) that already has an article_post")
            return article.articlepost_set[0].id

        TEMPORARY_EARLIEST_DATE = datetime.now(TIMEZONE) - timedelta(days=10)
        if article.published_parsed and article.published_parsed <= TEMPORARY_EARLIEST_DATE:
            log.info(f"article {article.id} skipped in post_article because it's too old: {article.published_parsed}")
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

    if exception and ("status code 500" in exception or "status code 502" in exception):
        server_error_count = r.incr(SERVER_ERROR_COUNT_KEY)
        log.warning(f"incrementing server_error_count ({server_error_count})")

        # to do - actually - create retry regardless?
        if server_error_count >= MAX_SERVER_ERROR_COUNT:
            log.warning(f"not posting article {article.id} because of recent 500 errors ({server_error_count})")
            create_retry(article, article_post)

    # sleep longer if a call was made to an external service (avoids http 429s)
    if remote_metadata_lookup:
        time.sleep(3)
    else:
        time.sleep(1)

    return article_post.id
