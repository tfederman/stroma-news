import os

import boto3

SUCCESS_QUEUE_URL = os.environ["SUCCESS_QUEUE_URL"]


if __name__=="__main__":

    sqs = boto3.client('sqs')
    f = open("sqs.log", "a")

    fields = ['did','feed','limit','cursor','items_sent']

    while True:
        response = sqs.receive_message(QueueUrl=SUCCESS_QUEUE_URL,
                        MaxNumberOfMessages=10,
                        MessageAttributeNames=fields)

        if not response.get('Messages'):
            break

        # entries for deletion
        Entries = []

        for msg in response['Messages']:
            print(",".join([str(msg['MessageAttributes'].get(f,{}).get('StringValue','')) for f in fields]))
            f.write(",".join([str(msg['MessageAttributes'].get(f,{}).get('StringValue','')) for f in fields]) + "\n")
            Entries.append({'Id': msg['MessageId'], 'ReceiptHandle': msg['ReceiptHandle']})

        response = sqs.delete_message_batch(QueueUrl=SUCCESS_QUEUE_URL, Entries=Entries)
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200, f"sqs delete failure: {response['HTTPStatusCode']}"

    f.close()
