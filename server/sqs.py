import os

import boto3

sqs = boto3.client('sqs')

SQS_QUEUE_URL_SUCCESS = os.environ["SQS_QUEUE_URL_SUCCESS"]
SQS_QUEUE_URL_FAILURE = os.environ["SQS_QUEUE_URL_FAILURE"]

def send_sqs_success(feed, did, post_count):
    send_sqs("success", SQS_QUEUE_URL_SUCCESS, feed, did, post_count)

def send_sqs_failure(body):
    send_sqs(body, SQS_QUEUE_URL_FAILURE)

def send_sqs(body, url, feed="feed", did="did", post_count=0):
    sqs.send_message(
        QueueUrl=url,
        MessageAttributes={
            'did': {
                'DataType': 'String',
                'StringValue': did
            },
            'feed': {
                'DataType': 'String',
                'StringValue': feed
            },
            'post_count': {
                'DataType': 'Number',
                'StringValue': str(post_count)
            }
        },
        MessageBody=body,
    )
