from datetime import datetime

from redis import Redis
from rq import Queue

from database.models import ConvoMessage
from settings import log, QUEUE_NAME_MAIL, bsky
from mailbox.process import process_message


def get_facet_link(message):
    facets = getattr(message, "facets", [])
    try:
        facet = facets[0]
    except IndexError:
        return

    for feature in facet.features:
        if getattr(feature, "$type") == "app.bsky.richtext.facet#link":
            return feature.uri


def get_and_save_messages():

    convo_logs = bsky.get_convo_logs()

    # constant timestamp for messages received in this batch
    received_at = datetime.now()
    messages = []

    for convo_log in convo_logs.logs:
        event_type = getattr(convo_log, "$type")
        if event_type == "chat.bsky.convo.defs#logCreateMessage":
            try:
                profile = bsky.get_user_profile(convo_log.message.sender.did)
            except Exception as e:
                if "AccountTakedown" in str(e):
                    log.info(
                        f"Sender account {convo_log.message.sender.did} no longer exists: AccountTakedown"
                    )
                    continue
                else:
                    raise

            # if the cursor decorator on get_convo_logs is working correctly, each message
            # should only be returned by the API once which will avoid integrity errors
            facet_link = get_facet_link(convo_log.message)
            cm = ConvoMessage.create(
                message_id=convo_log.message.id,
                convo_id=convo_log.convoId,
                sender_did=convo_log.message.sender.did,
                sender=profile,
                text=convo_log.message.text,
                sent_at=convo_log.message.sentAt,
                received_at=received_at,
                facet_link=facet_link,
            )
            messages.append(cm)

    messages += list(
        ConvoMessage.select().where(
            ConvoMessage.processed_at.is_null(), ConvoMessage.process_error.is_null()
        )
    )

    for cm in messages:
        q = Queue(QUEUE_NAME_MAIL, connection=Redis())
        q.enqueue(process_message, cm, result_ttl=14400)

    return len(messages)
