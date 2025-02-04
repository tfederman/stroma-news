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

"""
Notes:

to update function code:
- cd server && zip bsky-server.zip *.py && aws lambda update-function-code --function-name bsky_server --zip-file fileb://bsky-server.zip

to update function config:
- aws lambda update-function-configuration --function-name bsky_server --handler server.lambda_handler

to create a function:
aws lambda create-function --function-name bsky_xxx \
--runtime python3.13 --handler server.lambda_handler \
--role arn:xxx \
--zip-file fileb://bsky.zip
"""
