#!/usr/bin/env python

import psycopg2

from settings import bsky

con = psycopg2.connect()
cursor = con.cursor()

feed = bsky.get_author_feed(actor=bsky.did, cursor=None, page_count=50)
posts = [p.post for p in feed.feed if p.post.labels]

for p in posts:
    fields = [
        p.uri.split("/")[-1],
        p.labels[0].val,
        p.embed.external.uri,
        p.embed.external.title,
        p.record.createdAt,
        False,
    ]
    
    placeholders = ",".join("%s" for _ in fields)
    try:
        cursor.execute(f"insert into labels values({placeholders})", fields)
        con.commit()
    except psycopg2.IntegrityError:
        con.rollback()
        continue

con.close()
