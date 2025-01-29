from datetime import datetime, timezone

import peewee

from bsky.client import Session
from media.card import get_post
from database import db


if __name__ == "__main__":

    db.connect()
    session = Session()

    feed_title, title, link, description, published_parsed, author = db.execute_sql("""
        select feed.title, a.title, link, summary, a.published_parsed, author
        from article a
            inner join fetch f on f.id=a.fetch_id
            inner join feed on feed.id=f.feed_id
        order by random() limit 1;""").fetchone()

    post = get_post(session, feed_title, title, link, description, published_parsed, author)

    print(session.create_record(post))
