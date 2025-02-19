from datetime import datetime

from redis import Redis
from rq import Queue

from bsky import session
from database.models import BskyUserProfile, ConvoMessage
from settings import log, QUEUE_NAME_MAIL
#from mailbox.process import process_messages


def get_and_save_messages():

    convo_logs = session.get_convo_logs()

    # constant timestamp for messages received in this batch
    received_at = datetime.now()
    counter = 0

    for convo_log in convo_logs.logs:
        event_type = getattr(convo_log, "$type")
        if event_type == "chat.bsky.convo.defs#logCreateMessage":
            try:
                profile = BskyUserProfile.get_or_create_from_api(convo_log.message.sender.did, session)
            except Exception as e:
                if "AccountTakedown" in str(e):
                    log.info(f"Sender account {convo_log.message.sender.did} no longer exists: AccountTakedown")
                    continue
                else:
                    raise

            # if the cursor decorator on get_convo_logs is working correctly, each message
            # should only be returned by the API once which will avoid integrity errors
            facet_link = ConvoMessage.get_facet_link(convo_log.message)
            cm = ConvoMessage.create(message_id=convo_log.message.id, convo_id=convo_log.convoId,
                    sender_did=convo_log.message.sender.did, sender=profile, text=convo_log.message.text,
                    sent_at=convo_log.message.sentAt, received_at=received_at, facet_link=facet_link)
            counter += 1

    if counter > 0:
        q = Queue(QUEUE_NAME_MAIL, connection=Redis())
        q.enqueue(process_messages, result_ttl=14400)

    return counter
