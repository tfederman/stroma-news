import os
import json

from feed import FEEDS, get_feed_items
from auth import get_user_did
from util import response
from sqs import send_sqs

CUSTOM_FEED_HOSTNAME = os.environ["CUSTOM_FEED_HOSTNAME"]

DEFAULT_DID = os.environ["DEFAULT_DID"]
FORCE_DEFAULT_DID = os.environ["FORCE_DEFAULT_DID"].lower() == "true"
DEFAULT_FEED = FEEDS[0]["uri"]


def failure(event):
    raise Exception("simulated exception")


def get_feed_skeleton(event):

    params = event.get("queryStringParameters", {})
    feed_id = params.get("feed", DEFAULT_FEED)
    cursor = params.get("cursor")
    limit = int(params.get("limit") or 24)

    short_feed_id = feed_id.split("/")[-1]

    try:
        if FORCE_DEFAULT_DID:
            did = DEFAULT_DID
            default_did = True
        else:
            did = get_user_did(event["headers"]["authorization"])
            default_did = False
    except Exception as e:
        print(f"+++ get_user_did exception: {e.__class__.__name__} - {e}")
        did = DEFAULT_DID
        default_did = True

    print(
        f"+++ feed: {short_feed_id}, limit: {limit}, cursor: {cursor}, did: {did}{' (default)' if default_did else ''}"
    )

    feed = get_feed_items(short_feed_id, did, limit, cursor)
    items_sent = len(feed["feed"])
    send_sqs("success", short_feed_id, limit, cursor, did, items_sent)

    return {
        "statusCode": 200,
        "body": json.dumps(feed),
    }


def describe_feed_generator(event):
    return response(
        {
            "encoding": "application/json",
            "body": {"did": f"did:web:{CUSTOM_FEED_HOSTNAME}", "feeds": FEEDS},
        }
    )


def did_json(event):
    r = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": f"did:web:{CUSTOM_FEED_HOSTNAME}",
        "service": [
            {
                "id": "#bsky_fg",
                "type": "BskyFeedGenerator",
                "serviceEndpoint": f"https://{CUSTOM_FEED_HOSTNAME}",
            }
        ],
    }
    return response(r)


def default(event, suffix=""):
    return response({"statusCode": 200, "body": f"Stroma feed generator{suffix}"})
