from datetime import datetime

from redis import Redis
from rq import Queue

from settings import log, QUEUE_NAME_FETCH
from feeds.user import build_user_feed
from feeds.tasks import fetch_feed_task, save_articles_task
from utils.filesystem import upload_user_feed_to_s3
from database.models import ConvoMessage, UserFeedSubscription, Feed, UserTextFilter


class ActionFailed(Exception):
    pass

def get_feed_by_uri(uri, create=True):

    feeds = Feed.select().where(
        (Feed.uri==f"{uri}") | (Feed.uri==f"{uri}/") |
        (Feed.uri==f"https://{uri}") | (Feed.uri==f"http://{uri}") |
        (Feed.uri==f"https://{uri}/") | (Feed.uri==f"http://{uri}/") |
        (Feed.site_href==f"{uri}") | (Feed.site_href==f"{uri}/") |
        (Feed.site_href==f"https://{uri}") | (Feed.site_href==f"http://{uri}") |
        (Feed.site_href==f"https://{uri}/") | (Feed.site_href==f"http://{uri}/")
    )

    try:
        return feeds[0], False
    except IndexError:
        if create:
            return Feed.create(uri=uri), True
        else:
            return None, False


def subscribe(uri, cm):

    log.info(f"subscribe {cm.sender.handle} to {uri}")
    uri = cm.facet_link or uri
    feed, feed_created = get_feed_by_uri(uri)
    log.info(f"feed: {feed.id} (created: {feed_created})")

    if not feed:
        raise ActionFailed(f"Feed to subscribe to not found for {uri}")

    q = Queue(QUEUE_NAME_FETCH, connection=Redis())
    sub = UserFeedSubscription.create(user=cm.sender, feed=feed)
    log.info(f"subscription id {sub.id}")

    # if rss feed is new, then first fetch it and next rebuild/upload requesting user's feed.
    # if rss feed is existing, only rebuild user's feed.
    if feed_created:
        log.info(f"queue fetch and save tasks (for {cm.sender.handle})")
        job_fetch = q.enqueue(fetch_feed_task, feed.id, result_ttl=14400)
        job_save  = q.enqueue(save_articles_task, cm.sender, depends_on=job_fetch, result_ttl=14400)
    else:
        log.info(f"queue build and upload feed jobs (for {cm.sender.handle})")
        build_user_feed_job = q.enqueue(build_user_feed, cm.sender)
        upload_job = q.enqueue(upload_user_feed_to_s3, cm.sender, depends_on=build_user_feed_job)


def unsubscribe(uri, cm):

    feed, created = get_feed_by_uri(uri, create=False)

    if feed:
        sub = UserFeedSubscription.get_or_none(user=cm.sender, feed=feed)
        if sub:
            sub.active = False
            sub.save()
        else:
            raise ActionFailed(f"Subscription to remove not found for user {sender.id}, uri {uri}")
    else:
        raise ActionFailed(f"Feed to remove not found for user {sender.id}, uri {uri}")


def remove_quotes(text):
    if text[0] in ["'",'"']:
        text = text[1:]
    if text[-1] in ["'",'"']:
        text = text[:-1]
    return text

def add_filter(text, cm):
    text = remove_quotes(text)
    UserTextFilter.create(user=cm.sender, text=text)
    log.info(f"filter added for user {cm.sender.handle} ({text})")

def remove_filter(text, cm):
    text = remove_quotes(text)
    rows_deleted = UserTextFilter.delete().where(UserTextFilter.user==cm.sender, UserTextFilter.text==text).execute()
    logfunc = log.info if rows_deleted == 1 else log.warning
    logfunc(f"{rows_deleted} filter rows deleted for user {cm.sender.handle} ({text})")


if __name__=="__main__":

    ACTIONS = {
        "subscribe": subscribe,
        "unsubscribe": unsubscribe,
        "filter": add_filter,
        "unfilter": remove_filter,
        #"list": list_subscriptions,
    }

    for cm in ConvoMessage.select().where(ConvoMessage.processed_at.is_null()):
        try:
            action, obj = cm.text.strip().split(" ", 1)
        except Exception as e:
            cm.process_error = f"{e.__class__.__name__}: {e}"
            log.error(f"error parsing message {cm.id}: {cm.process_error}")
            action = None

        if action:
            action = action.lower()
            if action in ACTIONS:
                try:
                    ACTIONS[action](obj, cm)
                except Exception as e:
                    cm.process_error = f"{e.__class__.__name__}: {e}"
                    log.error(f"error processing message {cm.id}: {cm.process_error}")
            else:
                cm.process_error = f"action not found for message {cm.id}: {action}"
                log.error(f"error processing message {cm.id}: {cm.process_error}")

        cm.processed_at = datetime.now()
        cm.save()
