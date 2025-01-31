from datetime import datetime

import peewee

from bsky import session
from database.models import BskyUserProfile, ConvoMessage

def get_and_save_messages(session):

    convo_logs = session.get_convo_logs()

    # constant timestamp for messages received in this batch
    received_at = datetime.now()
    counter = 0

    for log in convo_logs.logs:
        event_type = getattr(log, "$type")
        if event_type == "chat.bsky.convo.defs#logCreateMessage":
            profile = BskyUserProfile.get_or_create_from_api(log.message.sender.did, session)

            # if the cursor decorator on get_convo_logs is working correctly, each message
            # should only be returned by the API once which will avoid integrity errors
            cm = ConvoMessage.create(message_id=log.message.id, convo_id=log.convoId,
                    sender_did=log.message.sender.did, sender=profile, text=log.message.text,
                    sent_at=log.message.sentAt, received_at=received_at)
            counter += 1

    return counter


if __name__=="__main__":
    get_and_save_messages(session)
