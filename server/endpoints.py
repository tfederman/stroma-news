import os
import json

from feed import FEEDS, placeholder_feed_items
from auth import get_user_did
from util import response

CUSTOM_FEED_HOSTNAME = os.environ["CUSTOM_FEED_HOSTNAME"]


def get_feed_skeleton(event):

    try:
        iss_did = get_user_did(event["headers"]["authorization"])
    except Exception as e:
        iss_did = str(e)

    feed = placeholder_feed_items()

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

def default(event):
    return response({'statusCode': 200, 'body': f'Stroma feed generator'})
