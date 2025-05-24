#!/usr/bin/env python

import json
import time
import subprocess

import psycopg2

from settings import bsky, S3_BUCKET, S3_PREFIX
from pysky import APIError

con = psycopg2.connect()
cursor = con.cursor()
now = int(time.time())
posts = []

sql = "select post_id from labels where deleted='f' order by timestamp desc limit 24"
cursor.execute(sql)
rows = list(cursor)
for row in rows:
    rkey = row[0]
    time.sleep(0.25)
    try:
        post = bsky.get(endpoint="xrpc/com.atproto.repo.getRecord", repo=bsky.did, collection="app.bsky.feed.post", rkey=rkey)
        posts.append(rkey)
    except APIError as e:
        if "Could not locate record" in e.apilog.exception_text:
            print(f"marking {rkey} deleted")
            sql = "update labels set deleted='t' where post_id=%s"
            cursor.execute(sql, (rkey,))
            con.commit()
            

feed = {"feed": [{"cursor": now-n, "post": f"at://{bsky.did}/app.bsky.feed.post/{p}"} for n,p in enumerate(posts)]}
open("/tmp/labels-feed.json", "w").write(json.dumps(feed))
cmd = ["aws", "--quiet", "s3", "cp", "/tmp/labels-feed.json", f"s3://{S3_BUCKET}/{S3_PREFIX}/"]
subprocess.check_call(cmd)
