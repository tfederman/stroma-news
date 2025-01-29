import os
from datetime import datetime

import peewee
from peewee import CharField, DateTimeField, IntegerField, ForeignKeyField

from .fields import SHA1HashedField

db = peewee.SqliteDatabase(f"{os.path.dirname(os.path.abspath(__file__))}/stroma.db")


class BaseModel(peewee.Model):
    class Meta:
        database = db


class BskySession(BaseModel):
    accessJwt = SHA1HashedField()
    refreshJwt = SHA1HashedField()
    did = CharField()
    created_at = DateTimeField()
    create_method = IntegerField()
    exception = CharField(null=True)

    class Meta:
        table_name = "bsky_session"


class Feed(BaseModel):
    uri = CharField(unique=True)
    added_at = DateTimeField(default=datetime.utcnow)
    title = CharField(null=True)
    subtitle = CharField(null=True)
    site_href = CharField(null=True)


class Fetch(BaseModel):
    feed = ForeignKeyField(Feed)
    version = CharField(null=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = IntegerField(null=True)
    updated = CharField(null=True)
    updated_parsed = DateTimeField(null=True)
    etag = CharField(null=True)
    modified = CharField(null=True)
    modified_parsed = DateTimeField(null=True)
    href = CharField(null=True)
    exception = CharField(null=True)
    etag_sent = CharField(null=True)
    modified_sent = CharField(null=True)
    http_duration = peewee.DecimalField(null=True)
    # alter table fetch add column http_duration decimal


class Article(BaseModel):
    fetch = ForeignKeyField(Fetch)
    link = CharField()
    title = CharField(null=True)
    entry_id = CharField(null=True, unique=True)
    summary = CharField(null=True)
    author = CharField(null=True)
    tags = CharField(null=True)
    updated = DateTimeField(null=True)
    updated_parsed = DateTimeField(null=True)
    published = CharField(null=True)
    published_parsed = DateTimeField(null=True)


class ArticlePost(BaseModel):
    article = ForeignKeyField(Article)
    posted_at = DateTimeField(default=datetime.utcnow)
    post_url = CharField(null=True)
    exception = CharField(null=True)
    status = IntegerField(null=True)


if __name__=="__main__":

    if db.is_closed():
        db.connect()
        db.create_tables([BskySession, Feed, Fetch, Article, ArticlePost])
