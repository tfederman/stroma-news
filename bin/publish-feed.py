#!/usr/bin/env python

import os
from datetime import datetime, UTC

from settings import bsky

HOSTNAME = os.environ["CUSTOM_FEED_HOSTNAME"]
RECORD_NAME = "longtail-random"
#FEED_URI = f"at://{bsky.did}/app.bsky.feed.generator/{RECORD_NAME}"
DISPLAY_NAME = "Longtail Roulette"
DESCRIPTION = "48 random links from the last 48 hours, updated every 10 minutes"


def main():

    icon_path = "./assets/die.jpg"

    with open(icon_path, "rb") as f:
        icon_data = f.read()
        blob_response = bsky.upload_blob(icon_data, "image/jpeg")
        print(blob_response)

    collection = "app.bsky.feed.generator"
    rkey = "longtail-random"
    record = {
        "did": f"did:web:{HOSTNAME}",
        "displayName": DISPLAY_NAME,
        "description": DESCRIPTION,
        "avatar": blob_response.json["blob"],
        "createdAt": datetime.now(UTC).isoformat(),
    }

    response = bsky.put_record(collection, record, rkey)
    print(response)


if __name__=="__main__":
    main()
