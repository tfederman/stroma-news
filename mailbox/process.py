from datetime import datetime

from settings import log
from mailbox.actions import subscribe, unsubscribe, add_filter, remove_filter


ACTIONS = {
    "subscribe": subscribe,
    "unsubscribe": unsubscribe,
    "filter": add_filter,
    "unfilter": remove_filter,
}

def process_message(cm):

    if cm.processed_at:
        log.error(f"tried to process already-processed message {cm.id}")
        return

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
