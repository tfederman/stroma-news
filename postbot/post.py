import time
import traceback
from datetime import datetime, timedelta

import redis

from bsky import session
from settings import log, TIMEZONE
from media.card import get_post
from database.models import Article, ArticlePost, ArticlePostRetry

MAX_SERVER_ERROR_COUNT = 10
SERVER_ERROR_RECENCY_SECONDS = 300
SERVER_ERROR_TIMESTAMPS_KEY = "server_error_timestamps"
SERVER_ERROR_TIMESTAMPS_MAX_LENGTH  = MAX_SERVER_ERROR_COUNT * 4
SERVER_ERROR_TIMESTAMPS_TRIM_LENGTH = MAX_SERVER_ERROR_COUNT * 2
SERVER_STRUGGLE_BEGIN_KEY = "struggle_begin_timestamp"
SERVER_STRUGGLE_BACKOFF_DURATION = 900


def server_is_struggling():

    r = redis.Redis()
    struggle_begin_timestamp = r.get(SERVER_STRUGGLE_BEGIN_KEY)
    if struggle_begin_timestamp and time.time() - int(struggle_begin_timestamp) < SERVER_STRUGGLE_BACKOFF_DURATION:
        return True, 0, float(struggle_begin_timestamp)

    error_timestamps = r.lrange(SERVER_ERROR_TIMESTAMPS_KEY, 0, SERVER_ERROR_TIMESTAMPS_MAX_LENGTH+1)

    # reduce number of trims by trimming from [100] down to [50]
    # and then allow the list to get back up to [100] elements
    # rather than constantly trim from [100] down to [99]
    if len(error_timestamps) > SERVER_ERROR_TIMESTAMPS_MAX_LENGTH:
        r.ltrim(SERVER_ERROR_TIMESTAMPS_KEY, 0, SERVER_ERROR_TIMESTAMPS_TRIM_LENGTH)

    recent_errors = sum(1 for t in error_timestamps if time.time() - float(t) < SERVER_ERROR_RECENCY_SECONDS)
    if recent_errors >= MAX_SERVER_ERROR_COUNT:
        r.set(SERVER_STRUGGLE_BEGIN_KEY, time.time())
        return True, recent_errors, time.time()

    return False, recent_errors, None


def create_retry(article, article_post=None, td=None):
    td = td or timedelta(minutes=10)
    retry_at = datetime.now(TIMEZONE) + td
    ArticlePostRetry.create(article=article, article_post=article_post, retry_at=retry_at)


def post_article(article_id):

    article = Article.get(Article.id==article_id)

    struggling, recent_error_count, struggle_begin_timestamp = server_is_struggling()
    if struggling:
        started_at = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(struggle_begin_timestamp))
        log.warning(f"not posting article {article.id} because of recent 500 errors (flagged at: {started_at})")
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

        terms = [line.strip() for line in open("ignore-terms.txt")]
        external = post["embed"]["external"]
        filter_check_str = (external.get("title") or "") + (external.get("description") or "")
        if any(t.lower() in filter_check_str.lower() for t in terms):
            return

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
        r = redis.Redis()
        r.lpush(SERVER_ERROR_TIMESTAMPS_KEY, time.time())
        recent_error_count += 1
        log.warning(f"logging new 500 range server error (recent count: {recent_error_count}) (and creating retry for article {article.id})")
        create_retry(article, article_post)

    # sleep longer if a call was made to an external service (avoids http 429s)
    if remote_metadata_lookup:
        time.sleep(3)
    else:
        time.sleep(1)

    return article_post.id
