import subprocess

import boto3

from settings import log, S3_BUCKET, S3_PREFIX, LOCAL_FEED_PATH


def sync_all_to_s3():
    log.info("syncing files to s3...")
    cmd = ["aws", "--quiet", "s3", "sync", f"{LOCAL_FEED_PATH}/", f"s3://{S3_BUCKET}/{S3_PREFIX}/"]
    subprocess.check_call(cmd)


def upload_user_feed_to_s3(user):
    short_did = user.did.replace("did:plc:", "")
    filename = f"{LOCAL_FEED_PATH}/{short_did}.json"
    feed_json = open(filename).read()
    client = boto3.client('s3')
    client.put_object(Body=feed_json, Bucket=S3_BUCKET, Key=f"{S3_PREFIX}/{short_did}.json")
    return f"{S3_PREFIX}/{short_did}.json"
