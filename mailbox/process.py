from datetime import datetime

from settings import log, bsky
from mailbox.actions import add_feed, add_term, remove_feed, remove_term, add_filter_term, remove_filter_term
from database.models import Article, ArticlePost, UserFeedSubscription, UserTermSubscription, UserTermFilter


COMMANDS = [
    ("add filter term", add_filter_term),
    ("add feed", add_feed),
    ("add term", add_term),
    ("add", add_feed),
    ("remove filter term", remove_filter_term),
    ("remove feed", remove_feed),
    ("remove term", remove_term),
    ("remove", remove_feed),
]


def process_message(cm):

    log.info(f"#{cm.id}: process_message({cm.id})")
    if cm.processed_at:
        log.error(f"#{cm.id}: tried to process already-processed message")
        return
    elif cm.sender.handle == "longtail.news":
        log.error(f"#{cm.id}: skipping own message")
        cm.processed_at = datetime.now()
        cm.save()
        return

    message_text = cm.text.strip()
    log.info(f"#{cm.id}: message_text: {message_text}")
    log.info(f"#{cm.id}: facet_link: {cm.facet_link}")

    try:
        for command, command_func in COMMANDS:
            if message_text.lower().startswith(command + " "):
                message_text = message_text[len(command)+1:]
                command_func(cm, message_text)
                break
        else:
            if cm.facet_link or message_text.lower().startswith("http"):
                add_feed(cm, message_text) #, cm.facet_link or message_text)
            else:
                cm.reply = f"A message in this format is not understood. See a description of how to format messages at: https://longtail.news/ ({cm.id})"

    except Exception as e:
        log.error(f"#{cm.id}: {e.__class__.__name__}: {e}")
        cm.process_error = f"#{cm.id}: {e.__class__.__name__}: {e}"
        cm.processed_at = datetime.now()
        cm.reply = f"There was an error processing your message, sorry! A human will look into it. ({cm.id})"
        cm.send_reply(bsky)
        cm.save()
        raise

    if cm.reply:
        cm.send_reply(bsky)
    else:
        log.warning(f"#{cm.id}: no message reply")

    cm.processed_at = datetime.now()
    cm.save()
