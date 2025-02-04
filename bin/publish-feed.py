import os

from atproto import Client, models

HANDLE = os.environ["BSKY_AUTH_USERNAME"]
PASSWORD = os.environ["BSKY_AUTH_PASSWORD"]
HOSTNAME = os.environ["CUSTOM_FEED_HOSTNAME"]
FEED_URI = 'at://did:plc:o6ggjvnj4ze3mnrpnv5oravg/app.bsky.feed.generator/stroma-test'
RECORD_NAME = 'stroma-test'
DISPLAY_NAME = 'Stroma Test'
DESCRIPTION = 'Test of Stroma code'
AVATAR_PATH = "../assets/atom.png"
SERVICE_DID = f"did:web:{HOSTNAME}"

def main():
    client = Client()
    client.login(HANDLE, PASSWORD)

    feed_did = SERVICE_DID
    if not feed_did:
        feed_did = f'did:web:{HOSTNAME}'

    avatar_blob = None
    if AVATAR_PATH:
        with open(AVATAR_PATH, 'rb') as f:
            avatar_data = f.read()
            avatar_blob = client.upload_blob(avatar_data).blob

    response = client.com.atproto.repo.put_record(models.ComAtprotoRepoPutRecord.Data(
        repo=client.me.did,
        collection=models.ids.AppBskyFeedGenerator,
        rkey=RECORD_NAME,
        record=models.AppBskyFeedGenerator.Record(
            did=feed_did,
            display_name=DISPLAY_NAME,
            description=DESCRIPTION,
            avatar=avatar_blob,
            created_at=client.get_current_time_iso(),
        )
    ))

    print('Feed URI (put in "FEED_URI" env var):', response.uri)


if __name__ == '__main__':
    main()
