#!/usr/bin/env python

import os
from datetime import datetime, UTC

from settings import bsky

HOSTNAME = os.environ["CUSTOM_FEED_HOSTNAME"]

# change these settings per feed
#RECORD_NAME = "longtail-random"
#DISPLAY_NAME = "Longtail Roulette"
#DESCRIPTION = "48 random links from the last 48 hours, updated every 30 minutes"
#ICON_PATH = "./assets/die.jpg"
#ICON_TYPE = "image/jpeg"

#RECORD_NAME = "longtail-random-90"
#DISPLAY_NAME = "Longtail Roulette 90 day"
#DESCRIPTION = "48 random links from the last 90 days, updated every 30 minutes"
#ICON_PATH = "./assets/die.jpg"
#ICON_TYPE = "image/jpeg"

RECORD_NAME = "longtail-labeled"
DISPLAY_NAME = "Labeled Longtail posts"
DESCRIPTION = "Posts that were labeled by Bluesky moderation (helps me find and remove nsfw feeds)"
ICON_PATH = "./assets/18b.png"
ICON_TYPE = "image/png"

def main():

    with open(ICON_PATH, "rb") as f:
        icon_data = f.read()
        blob_response = bsky.upload_blob(icon_data, ICON_TYPE)
        print(blob_response)

    collection = "app.bsky.feed.generator"
    rkey = RECORD_NAME
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
