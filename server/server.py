from endpoints import *
from sqs import send_sqs_failure

dispatch_map = {
    "/xrpc/app.bsky.feed.describeFeedGenerator": describe_feed_generator,
    "/.well-known/did.json": did_json,
    "/xrpc/app.bsky.feed.getFeedSkeleton": get_feed_skeleton,
    "/failure": failure,
    "/default": default,
}


def lambda_handler(event, context):
    try:
        path = event.get("rawPath") or "/default"
        return dispatch_map.get(path, default)(event)
    except Exception as e:
        print(f"+++ DISPATCH EXCEPTION {e.__class__.__name__} - {e}")
        send_sqs_failure(f"{e.__class__.__name__} - {e}")
        return default(event, ".")


"""
Notes:

to update function code:
- cd server && zip bsky-server.zip *.py && aws lambda update-function-code --function-name bsky_02 --zip-file fileb://bsky-server.zip

to update function config:
- aws lambda update-function-configuration --function-name bsky_server --handler server.lambda_handler

to create a function:
aws lambda create-function --function-name bsky_xxx \
--runtime python3.13 --handler server.lambda_handler \
--role arn:xxx \
--zip-file fileb://bsky.zip
"""
