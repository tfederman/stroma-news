import os
import json

from feed import FEEDS, get_feed_items
from auth import get_user_did
from util import response
from sqs import send_sqs_success

CUSTOM_FEED_HOSTNAME = os.environ["CUSTOM_FEED_HOSTNAME"]

DEFAULT_DID = "did:plc:5euo5vsiaqnxplnyug3k3art"
DEFAULT_FEED = FEEDS[0]["uri"]


def failure(event):
    raise Exception("simulated exception")


def get_feed_skeleton(event):

    feed_id = event.get("queryStringParameters", {}).get("feed", DEFAULT_FEED)
    short_feed_id = feed_id.split("/")[-1]

    try:
        did = get_user_did(event["headers"]["authorization"])
        default_did = False
    except Exception as e:
        print(f"+++ get_user_did exception: {e.__class__.__name__} - {e}")
        did = DEFAULT_DID
        default_did = True

    print(f"+++ feed: {short_feed_id}, did: {did}{' (default)' if default_did else ''}")

    feed = get_feed_items(short_feed_id, did)
    post_count = len(feed["feed"])
    send_sqs_success(short_feed_id, did, post_count)

    return {
        'statusCode': 200,
        'body': json.dumps(feed),
    }


def describe_feed_generator(event):
    return response({'encoding': 'application/json',
                        'body': {'did': f'did:web:{CUSTOM_FEED_HOSTNAME}',
                        'feeds': FEEDS}})

def did_json(event):
    r = {'@context': ['https://www.w3.org/ns/did/v1'],
            'id': f'did:web:{CUSTOM_FEED_HOSTNAME}',
            'service': [{
                'id': '#bsky_fg',
                'type': 'BskyFeedGenerator',
                'serviceEndpoint': f'https://{CUSTOM_FEED_HOSTNAME}'
            }]
        }
    return response(r)

def event_json(event):
    return response(event)

def default(event, suffix=""):
    return response({'statusCode': 200, 'body': f'Stroma feed generator{suffix}'})
