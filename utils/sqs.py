import os

import boto3

SUCCESS_QUEUE_URL = os.environ["SUCCESS_QUEUE_URL"]


if __name__=="__main__":

    sqs = boto3.client('sqs')

    response = sqs.receive_message(QueueUrl=SUCCESS_QUEUE_URL,
                    MaxNumberOfMessages=10,
                    MessageAttributeNames=['did','feed','post_count'])

    # entries for deletion
    Entries = []

    for msg in response['Messages']:
        # do something
        Entries.append({'Id': msg['MessageId'], 'ReceiptHandle': msg['ReceiptHandle']})

    response = sqs.delete_message_batch(QueueUrl=SUCCESS_QUEUE_URL, Entries=Entries)

    assert response["HTTPStatusCode"], f"sqs delete failure: {response['HTTPStatusCode']}"
