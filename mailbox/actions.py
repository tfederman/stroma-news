from urllib.parse import urlparse

from redis import Redis
from rq import Queue

from settings import log, QUEUE_NAME_FETCH
from feeds.user import build_user_feed
from feeds.tasks import fetch_feed_task, save_articles_task
from utils.filesystem import upload_user_feed_to_s3
from database.models import UserFeedSubscription, UserTermSubscription, Article, ArticlePost, Feed


def add_filter_term(cm, message_text):
    pass

def remove_filter_term(cm, message_text):
    pass


def add_feed(cm, message_text):
    url = cm.facet_link or message_text
    log.info(f"#{cm.id}: add_feed(\"{url}\")")
    feed = get_feed_from_url(cm, url)

    if feed and not feed.active:
        log.error(f'#{cm.id}: feed {feed.id} is inactive')
        cm.process_error = f'#{cm.id}: no active feed found for "{url}"'
        cm.reply = f"An active RSS feed for that URL was not found, sorry! ({cm.id})"
        return

    if not feed:
        cm.process_error = f'#{cm.id}: no feed found for "{url}"'
        cm.reply = f"An RSS feed for that URL was not found, sorry! ({cm.id})"
        return

    ufs, created = UserFeedSubscription.get_or_create(user=cm.sender, feed=feed)
    if created:
        cm.reply = f'The feed "{feed.title}" was added to your list.'
    else:
        cm.reply = f'The feed "{feed.title}" seems to be on your list already.'


def remove_feed(cm, message_text):

    url = cm.facet_link or message_text
    log.info(f"#{cm.id}: remove_feed(\"{url}\")")
    feed = get_feed_from_url(cm, url)

    if not feed:
        cm.process_error = f'#{cm.id}: no feed found for "{url}"'
        cm.reply = f"An RSS feed for that URL was not found, sorry! ({cm.id})"
        return

    delete_stmt = UserFeedSubscription.delete().where(UserFeedSubscription.user==cm.sender, UserFeedSubscription.feed==feed)
    rows_deleted = delete_stmt.execute()

    if rows_deleted > 0:
        cm.reply = f'The feed was removed from your list.'
    else:
        cm.reply = f'The feed was not removed because it was not found on your list, sorry! ({cm.id})'


def add_term(cm, message_text):

    uts, created = UserTermSubscription.get_or_create(user=cm.sender, term=message_text)
    if created:
        cm.reply = f'The term "{message_text}" was added to your list.'
    else:
        cm.reply = f'The term "{message_text}" seems to be on your list already.'


def remove_term(cm, message_text):

    delete_stmt = UserTermSubscription.delete().where(UserTermSubscription.user==cm.sender, UserTermSubscription.term==message_text)
    rows_deleted = delete_stmt.execute()

    if rows_deleted > 0:
        cm.reply = f'The term was removed from your list.'
    else:
        cm.reply = f'The term was not removed from your list. Perhaps you spelled it differently when adding it? ({cm.id})'


def get_feed_from_url(cm, url):
    p = urlparse(url)

    # is this a sufficient test for article url vs. bsky url?
    if p.netloc == "bsky.app":
        post_id = url.split("/")[-1]
        post = ArticlePost.get(ArticlePost.post_id==post_id)
        feed = post.article.feed_fetch.feed
    else:
        feed = Article.get_or_none(Article.link==url) or Feed.get_or_none(Feed.uri==url)
        if isinstance(feed, Article):
            feed = feed.feed_fetch.feed

        if not feed:
            # try getting new feed from url
            feed = get_feed_from_article(cm, url)

    if not feed:
        log.error(f'#{cm.id}: no feed found for "{url}"')
        return None

    return feed


def get_feed_from_article(cm, url):
    return None
