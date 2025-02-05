import json

import boto3

FEEDS = [
    {'uri': f'at://did:plc:o6ggjvnj4ze3mnrpnv5oravg/app.bsky.feed.generator/stroma-test'},
    {'uri': f'at://did:plc:5euo5vsiaqnxplnyug3k3art/app.bsky.feed.generator/tmf-test'},
]

def get_s3_object(did):

    short_did = did.replace("did:plc:", "")

    bucket = "stroma-news"
    key = f"feed-json/{short_did}.json"
    print(f"+++ key: {key}")

    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj['Body'].read())


def get_feed_items(feed, did):
    try:
        return get_s3_object(did)
    except Exception as e:
        print(f"+++ s3_test_feed_items exception: {e}")
        return placeholder_feed_items()


def placeholder_feed_items():
    return {'cursor': 'cursor',
            'feed': [
                {'post': 'at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3lh37fys3fo2a'},
                {'post': 'at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3lh22fx5vr22s'},
                {'post': 'at://did:plc:62h2n5ftyykdyyglbru4sjpd/app.bsky.feed.post/3lc3so7vffc2f'},
                {'post': 'at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3lgjm5jhofl2d'},
                {'post': 'at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3lginnuwwrk24'},
                {'post': 'at://did:plc:62h2n5ftyykdyyglbru4sjpd/app.bsky.feed.post/3lbk47jf3z22m'},
                {'post': 'at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3lfxyv2qsl42q'},
                {'post': 'at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3lfxa23kqpk27'},
                {'post': 'at://did:plc:62h2n5ftyykdyyglbru4sjpd/app.bsky.feed.post/3layhj27cds2s'},
                {'post': 'at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3lfgfmnhno52a'},
                {'post': 'at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3lffalrvzns2i'},
                {'post': 'at://did:plc:62h2n5ftyykdyyglbru4sjpd/app.bsky.feed.post/3l42l6lhxcy2z'},
                {'post': 'at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3leuse6ydyr2e'},
                {'post': 'at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3leuntfevsk2u'},
                {'post': 'at://did:plc:62h2n5ftyykdyyglbru4sjpd/app.bsky.feed.post/3l3ienxoous2s'},
                {'post': 'at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3led73r5asg2y'},
                {'post': 'at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3ledknbz3wc2m'},
                {'post': 'at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3ldrltesgy52s'},
                {'post': 'at://did:plc:uch7nbvmh452xplkgonrjd27/app.bsky.feed.post/3ldqgyvcyvs2b'},
                {'post': 'at://did:plc:zcmchxw2gxlbincrchpdjopq/app.bsky.feed.post/3ld7ykuvhow2m'}]}
