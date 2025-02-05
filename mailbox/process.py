from datetime import datetime

from settings import log
from database.models import ConvoMessage, UserFeedSubscription, Feed


class ActionFailed(Exception):
    pass

def get_feed_by_uri(uri, create=True):

    uri = uri.replace("?m=1", "")

    feeds = Feed.select().where(
        (Feed.uri==f"{uri}") | (Feed.uri==f"{uri}/") |
        (Feed.uri==f"https://{uri}") | (Feed.uri==f"http://{uri}") |
        (Feed.uri==f"https://{uri}/") | (Feed.uri==f"http://{uri}/") |
        (Feed.site_href==f"{uri}") | (Feed.site_href==f"{uri}/") |
        (Feed.site_href==f"https://{uri}") | (Feed.site_href==f"http://{uri}") |
        (Feed.site_href==f"https://{uri}/") | (Feed.site_href==f"http://{uri}/")
    )

    try:
        feed = feeds[0]
    except IndexError:
        if create:
            feed = Feed.create(uri=uri)
        else:
            feed = None

    return feed


def subscribe(uri, cm):

    feed = get_feed_by_uri(uri)

    if feed:
        sub = UserFeedSubscription.create(user=cm.sender, feed=feed)
    else:
        raise ActionFailed(f"Feed to subscribe to not found for {uri}")


def unsubscribe(uri, cm):

    feed = get_feed_by_uri(uri, create=False)

    if feed:
        sub = UserFeedSubscription.get_or_none(user=cm.sender, feed=feed)
        if sub:
            sub.active = False
            sub.save()
        else:
            raise ActionFailed(f"Subscription to remove not found for user {sender.id}, uri {uri}")
    else:
        raise ActionFailed(f"Feed to remove not found for user {sender.id}, uri {uri}")


if __name__=="__main__":

    ACTIONS = {
        "subscribe": subscribe,
        "unsubscribe": unsubscribe,
    }

    for cm in ConvoMessage.select().where(ConvoMessage.processed_at.is_null()):
        try:
            action, obj = cm.text.strip().split(" ", 1)
        except Exception as e:
            cm.process_error = f"{e.__class__.__name__}: {e}"
            log.error(f"error processing message {cm.id}: {cm.process_error}")
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
