#!/usr/bin/env python

import time
import json
import subprocess
from datetime import datetime, timedelta, UTC

from peewee import fn

from settings import log, S3_BUCKET, S3_PREFIX, bsky
from database.models import Article, ArticlePost

now = int(time.time())

feed_expressions = {
    "48-hour": [
        ArticlePost.post_id.is_null(False),
        ArticlePost.deleted.is_null(),
        ArticlePost.posted_at >= datetime.now(UTC) - timedelta(hours=48),
        ArticlePost.posted_at <= datetime.now(UTC) + timedelta(hours=4),
    ],
    "90-day": [
        ArticlePost.post_id.is_null(False),
        ArticlePost.deleted.is_null(),
        ArticlePost.posted_at >= datetime.now(UTC) - timedelta(days=90),
        ArticlePost.posted_at <= datetime.now(UTC) - timedelta(days=2),
    ],
}

for feedname, expr in feed_expressions.items():
    articles = Article.select().join(ArticlePost).where(*expr).order_by(fn.Random()).limit(48)

    feed = {"feed": [{"cursor": now-n, "post": f"at://{bsky.did}/app.bsky.feed.post/{a.articlepost_set[0].post_id}"} for n,a in enumerate(articles)]}

    FILENAME = f"/tmp/random-feed-{feedname}.json"

    open(FILENAME, "w").write(json.dumps(feed))

    cmd = ["aws", "--quiet", "s3", "cp", FILENAME, f"s3://{S3_BUCKET}/{S3_PREFIX}/"]
    subprocess.check_call(cmd)
