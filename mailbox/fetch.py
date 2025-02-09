from datetime import datetime

import peewee

from bsky import session
from database.models import BskyUserProfile, ConvoMessage
from settings import log


def get_and_save_messages(session):

    convo_logs = session.get_convo_logs()

    # constant timestamp for messages received in this batch
    received_at = datetime.now()
    counter = 0

    for convo_log in convo_logs.logs:
        event_type = getattr(convo_log, "$type")
        if event_type == "chat.bsky.convo.defs#logCreateMessage":
            profile = BskyUserProfile.get_or_create_from_api(convo_log.message.sender.did, session)

            # if the cursor decorator on get_convo_logs is working correctly, each message
            # should only be returned by the API once which will avoid integrity errors
            facet_link = ConvoMessage.get_facet_link(convo_log.message)
            cm = ConvoMessage.create(message_id=convo_log.message.id, convo_id=convo_log.convoId,
                    sender_did=convo_log.message.sender.did, sender=profile, text=convo_log.message.text,
                    sent_at=convo_log.message.sentAt, received_at=received_at, facet_link=facet_link)
            counter += 1

    return counter

if __name__=="__main__":
    get_and_save_messages(session)
