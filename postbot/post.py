import time
import traceback
from urllib.parse import urlparse
from datetime import datetime, timedelta, UTC

import redis

from pysky import UploadException, MediaException, RateLimitExceeded

from settings import bsky
from utils.backoff import log_server_error, server_is_struggling
from settings import log, TIMEZONE
from media.card import get_post
from database.models import Article, ArticlePost, ArticlePostRetry, FeedFetch, Feed


def create_post_retry(article, article_post=None, td=None):
    td = td or timedelta(minutes=10)
    retry_at = datetime.now(TIMEZONE) + td
    ArticlePostRetry.create(article=article, article_post=article_post, retry_at=retry_at)


def post_article(article_id, is_retry=False):

    article = (
        Article.select(Article, FeedFetch, Feed)
        .join(FeedFetch)
        .join(Feed)
        .where(Article.id == article_id)[0]
    )

    try:
        html_attr_lang = article.articlemeta_set[0].html_attr_lang.strip().lower()
        if html_attr_lang and not html_attr_lang.startswith("en"):
            return
    except:
        pass

    try:
        ignore_domains = [line for line in open("ignore-domains.txt") if line.strip()]
        if article.articlemeta_set:
            canonical_link = article.articlemeta_set[0].canonical_link
            if canonical_link:
                p = urlparse(canonical_link)

                # not the most desired behavior, www.ign.com is considered inactive but there's an active feed on the equivalent feeds.ign.com
                # inactive_subdomain = list(Feed.select(Feed.active).where(Feed.subdomain==p.netloc).distinct().tuples()) == [(False,)]
                #if inactive_subdomain:
                #    log.warning(f"skipping article {article.id} because of canonical_link domain (inactive_subdomain) {p.netloc}")
                #    return

                if any(d in p.netloc for d in ignore_domains):
                    log.warning(f"skipping article {article.id} because of canonical_link domain (ignore_domains) {p.netloc}")
                    return

    except Exception as e:
        log.warning(f"exception with canonical link check: {e}")
        pass

    try:
        if "bad content type for article" in article.articlemeta_set[0].exception:
            log.warning(f"not posting article {article_id} because of content type exception")
            return
    except:
        pass

    posts_from_feed_24hour = (
        Article.select()
        .join(FeedFetch)
        .join(Feed)
        .switch(Article)
        .join(ArticlePost)
        .where(Article.feed_fetch.feed==article.feed_fetch.feed,
               ArticlePost.post_id.is_null(False),
               ArticlePost.posted_at >= datetime.now(UTC) - timedelta(hours=24))
        .count()
    )

    if posts_from_feed_24hour >= 20:
        return

    struggling = server_is_struggling()
    if struggling:
        log.warning(
            f"not posting article {article.id} because of too many recent 500 errors (creating retry)"
        )
        create_post_retry(article)
        return

    try:
        if not article.feed_fetch.feed.active:
            return

        # disallow repeat article post unless the prior attempt had an exception
        if len(article.articlepost_set) > 0 and article.articlepost_set[0].exception is None:
            log.warning(f"tried to post article ({article.id}) that already has an article_post")
            return article.articlepost_set[0].id

        post, remote_metadata_lookup = get_post(bsky, article)

        terms = [line.strip("\r\n") for line in open("ignore-terms.txt")]
        title = post.external.title or ""
        description = post.external.description or ""
        filter_check_str = f"{title}:{description}:{article.link}"
        if any(t.lower() in filter_check_str.lower() for t in terms):
            return

        authors = [line.strip("\r\n").lower() for line in open("ignore-authors.txt") if line.strip("\r\n")]
        if article.author and article.author.lower() in authors:
            log.info(f"skipping article {article.id} because of author {article.author}")
            return

        try:
            for n in range(120):
                try:
                    response = bsky.create_post(post=post)
                    if n > 0:
                        log.warning(f"posted article {article.id} on rate limit attempt {n+1}")
                    break
                except RateLimitExceeded:
                    if n >= 39:
                        log.error(f"ran out of attempts to post rate-limited article {article.id}")
                        raise
                    time.sleep(30)

        except (MediaException, UploadException) as e:
            log.warning(f"uploading article {article.id} without media: {e.__class__.__name__} - {e}")
            response = bsky.create_post(post=post, skip_uploads=True)
        uri = response.uri
        post_id = response.uri.split("/")[-1]
        exception = None
        exception_to_raise = None
    except Exception as e:
        exception = f"{e.__class__.__name__} - {e}\n{traceback.format_exc()}"
        uri = None
        post_id = None
        remote_metadata_lookup = "cardy_lookup: True" in str(e)
        exception_to_raise = e

    if article.articlepost_set:
        article_post = article.articlepost_set[0]
        article_post.uri = uri
        article_post.post_id = post_id
        article_post.article = article
        article_post.exception = exception
        article_post.remote_metadata_lookup = remote_metadata_lookup
        article_post.posted_at = datetime.now(UTC)
        article_post.save()
    else:
        article_post = ArticlePost(
            uri=uri,
            post_id=post_id,
            article=article,
            exception=exception,
            remote_metadata_lookup=remote_metadata_lookup,
        )
        article_post.save()

    if exception and ("status code 500" in exception or "status code 502" in exception):
        log_server_error()

        if is_retry:
            log.error(f"pause and retry after 502 error failed again for article {article_id}")

        if ("status code 502" in exception or "status code 504" in exception) and not is_retry:
            log.info(f"pausing ten seconds and retrying post_article({article_id})")
            time.sleep(10)
            post_article(article_id, is_retry=True)
            exception_to_raise = None
        else:
            create_post_retry(article, article_post)

    if is_retry and article_post.exception is None:
        log.info(f"pause and retry was successful for article {article_id}")
    elif is_retry:
        log.info(f"pause and retry was NOT successful for article {article_id} - {article_post.exception}")

    # sleep longer if a call was made to an external service (avoids http 429s)
    if remote_metadata_lookup:
        time.sleep(2)
    else:
        time.sleep(0.8)

    if isinstance(exception_to_raise, Exception):
        raise exception_to_raise

    return article_post.id
