import os
import sys
import json

import boto3

BOF_CURSOR = sys.maxsize
EOF_CURSOR = "eof"

FEEDS = [
    {"uri": f"at://did:plc:o6ggjvnj4ze3mnrpnv5oravg/app.bsky.feed.generator/stroma-news"},
    {"uri": f"at://did:plc:o6ggjvnj4ze3mnrpnv5oravg/app.bsky.feed.generator/stroma-test"},
    {"uri": f"at://did:plc:5euo5vsiaqnxplnyug3k3art/app.bsky.feed.generator/tmf-test"},
]


def get_s3_feed(filename, limit, cursor):

    if cursor == EOF_CURSOR:
        return {"cursor": cursor, "feed": []}

    filename = filename.replace("did:plc:", "")

    bucket = os.environ["S3_BUCKET"]
    prefix = os.environ["S3_PREFIX"]
    key = f"{prefix}/{filename}.json"

    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    j = json.loads(obj["Body"].read())

    limit = limit or 24

    try:
        cursor = cursor or BOF_CURSOR
        cursor = int(cursor)
    except ValueError:
        cursor = BOF_CURSOR

    feed_items = []
    new_cursor = 0
    items_skipped = 0

    for item in j["feed"]:

        if item["cursor"] < cursor:
            feed_items.append({"post": item["post"]})
            new_cursor = item["cursor"]
        else:
            items_skipped += 1

        if len(feed_items) >= limit:
            break

    if items_skipped + len(feed_items) == len(j["feed"]):
        new_cursor = EOF_CURSOR

    feed = {"cursor": str(new_cursor), "feed": feed_items}
    return feed


def get_feed_items(feed, did, limit, cursor):
    try:
        if feed == "longtail-random":
            return get_s3_feed("random", limit, cursor)
        else:
            return get_s3_feed(did, limit, cursor)
    except Exception as e:
        print(f"+++ s3_test_feed_items exception: {e}")
        return placeholder_feed_items()[:limit]


def placeholder_feed_items():
    return {
        "cursor": EOF_CURSOR,
        "feed": [
            {"post": "at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3lh37fys3fo2a"},
            {"post": "at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3lh22fx5vr22s"},
            {"post": "at://did:plc:62h2n5ftyykdyyglbru4sjpd/app.bsky.feed.post/3lc3so7vffc2f"},
            {"post": "at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3lgjm5jhofl2d"},
            {"post": "at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3lginnuwwrk24"},
            {"post": "at://did:plc:62h2n5ftyykdyyglbru4sjpd/app.bsky.feed.post/3lbk47jf3z22m"},
            {"post": "at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3lfxyv2qsl42q"},
            {"post": "at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3lfxa23kqpk27"},
            {"post": "at://did:plc:62h2n5ftyykdyyglbru4sjpd/app.bsky.feed.post/3layhj27cds2s"},
            {"post": "at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3lfgfmnhno52a"},
            {"post": "at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3lffalrvzns2i"},
            {"post": "at://did:plc:62h2n5ftyykdyyglbru4sjpd/app.bsky.feed.post/3l42l6lhxcy2z"},
            {"post": "at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3leuse6ydyr2e"},
            {"post": "at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3leuntfevsk2u"},
            {"post": "at://did:plc:62h2n5ftyykdyyglbru4sjpd/app.bsky.feed.post/3l3ienxoous2s"},
            {"post": "at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3led73r5asg2y"},
            {"post": "at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3ledknbz3wc2m"},
            {"post": "at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3ldrltesgy52s"},
            {"post": "at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3ldqgyvcyvs2b"},
            {"post": "at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3ld7ykuvhow2m"},
        ],
    }


if __name__=="__main__":
    feed = get_s3_object("msleiqq55klucvzm33gdtjje", 8, "eof")
    print(json.dumps(feed, indent=4))
