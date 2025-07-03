from urllib.parse import urlparse

from redis import Redis
from rq import Queue

from settings import log, QUEUE_NAME_FETCH
from feeds.user import build_user_feed
from feeds.tasks import fetch_feed_task, save_articles_task
from utils.httputil import get_rss_from_url
from utils.filesystem import upload_user_feed_to_s3
from database.models import UserFeedSubscription, UserTermSubscription, UserTermFilter, Article, ArticlePost, Feed


def add_filter_term(cm, message_text):

    uts, created = UserTermFilter.get_or_create(user=cm.sender, term=message_text)
    if created:
        cm.reply = f'The term "{message_text}" was added to your filter list.'
    else:
        cm.reply = f'The term "{message_text}" seems to be on your filter list already.'


def remove_filter_term(cm, message_text):

    delete_stmt = UserTermFilter.delete().where(UserTermFilter.user==cm.sender, UserTermFilter.term==message_text)
    rows_deleted = delete_stmt.execute()

    if rows_deleted > 0:
        cm.reply = f'The term was removed from your filter list.'
    else:
        cm.reply = f'The term was not removed from your filter list. Perhaps you spelled it differently when adding it? ({cm.id})'


def add_feed(cm, message_text):
    url = cm.facet_link or message_text
    log.info(f"#{cm.id}: add_feed(\"{url}\")")
    feed, feed_created = get_feed_from_url(cm, url, True)

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
    if created and not feed_created:
        if feed.title:
            cm.reply = f'The feed "{feed.title}" was added to your list.'
        else:
            cm.reply = f'The feed was added to your list. (#{feed.id}) ({cm.id})'
    elif created and feed_created:
        cm.reply = f'A new feed was found and added to the system and to your list. Articles will show up after the site is first fetched.'
    else:
        cm.reply = f'The feed "{feed.title}" seems to be on your list already.'


def remove_feed(cm, message_text):

    url = cm.facet_link or message_text
    log.info(f"#{cm.id}: remove_feed(\"{url}\")")
    feed, created = get_feed_from_url(cm, url, False)

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


def get_feed_from_url(cm, url, attempt_create=False):
    p = urlparse(url)
    created = False

    # is this a sufficient test for article url vs. bsky url?
    if p.netloc == "bsky.app":
        post_id = url.split("/")[-1]
        post = ArticlePost.get(ArticlePost.post_id==post_id)
        feed = post.article.feed_fetch.feed
    else:
        feed = Article.get_or_none(Article.link==url) or Feed.get_or_none(Feed.uri==url)
        if isinstance(feed, Article):
            feed = feed.feed_fetch.feed

        if not feed and attempt_create:
            # try finding and creating a new feed from the article url
            feed = get_feed_from_article(cm, url)
            created = True

    if not feed:
        log.error(f'#{cm.id}: no feed found for "{url}"')
        return None, False

    return feed, created


def get_feed_from_article(cm, url):
    try:
        rss = get_rss_from_url(url)
        feed = Feed.create(uri=rss)
        return feed
    except Exception as e:
        log.error(f"#{cm.id}: get_feed_from_article - {e.__class__.__name__}: {e}")
        return None
