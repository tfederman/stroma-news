import os

import boto3

sqs = boto3.client('sqs')

SQS_QUEUE_URL_SUCCESS = os.environ["SQS_QUEUE_URL_SUCCESS"]
SQS_QUEUE_URL_FAILURE = os.environ["SQS_QUEUE_URL_FAILURE"]


def send_sqs_failure(body):
    sqs.send_message(
        QueueUrl=SQS_QUEUE_URL_FAILURE,
        MessageAttributes={},
        MessageBody=body,
    )


def send_sqs(body, feed, limit, cursor, did, items_sent):
    sqs.send_message(
        QueueUrl=SQS_QUEUE_URL_SUCCESS,
        MessageAttributes={
            'did': {'DataType': 'String', 'StringValue': did},
            'feed': {'DataType': 'String', 'StringValue': feed},
            'limit': {'DataType': 'Number', 'StringValue': str(limit)},
            'cursor': {'DataType': 'String', 'StringValue': cursor or "none"},
            'items_sent': {'DataType': 'Number', 'StringValue': str(items_sent)}
        },
        MessageBody=body,
    )
