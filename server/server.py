from endpoints import *

dispatch_map = {
    '/xrpc/app.bsky.feed.describeFeedGenerator': describe_feed_generator,
    '/.well-known/did.json': did_json,
    '/event': event_json,
    '/xrpc/app.bsky.feed.getFeedSkeleton': get_feed_skeleton,
    'default': default,
}

def lambda_handler(event, context):
    path = event.get('rawPath') or 'default'
    return dispatch_map.get(path, default)(event)
