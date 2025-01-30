import os
from datetime import datetime

import peewee
from peewee import DateTimeField, IntegerField, ForeignKeyField

from database import db
from database.fields import PostgreSQLCharField as CharField


class BaseModel(peewee.Model):
    class Meta:
        database = db


class BskySession(BaseModel):
    accessJwt = CharField()
    refreshJwt = CharField()
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
    image_url = CharField(null=True)


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
    updated = CharField(null=True)
    updated_parsed = DateTimeField(null=True)
    published = CharField(null=True)
    published_parsed = DateTimeField(null=True)


class ArticleMeta(BaseModel):
    article = ForeignKeyField(Article, unique=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    og_title = CharField(null=True)
    og_url = CharField(null=True)
    og_image = CharField(null=True)
    twitter_image = CharField(null=True)
    status = IntegerField(null=True)
    exception = CharField(null=True)
    text = CharField(null=True)

    class Meta:
        table_name = "article_meta"


class ArticlePost(BaseModel):
    article = ForeignKeyField(Article, unique=True)
    posted_at = DateTimeField(default=datetime.utcnow)
    post_id = CharField(null=True)
    exception = CharField(null=True)
    uri = CharField(null=True)

    class Meta:
        table_name = "article_post"


def migrate_pgsql(cls, con):
    """Migrate the data from the current sqlite db into a postgresql db"""
    rows = list(cls.select().order_by(cls.id).tuples())
    cursor = con.cursor()
    column_count = len(rows[0])
    column_placeholders = ",".join(["%s"] * column_count)
    cursor.executemany(f'INSERT INTO "{cls._meta.table_name}" VALUES ({column_placeholders})', rows)
    con.commit()


if __name__=="__main__":


    # migrate sqlite data to postgres
    # import psycopg2
    # con = psycopg2.connect("dbname=stroma ...")
    # for cls in [BskySession, Feed, Fetch, Article, ArticlePost, ArticleMeta]:
    #     print(f"migrating {cls._meta.table_name}...")
    #     migrate_pgsql(cls, con)

    # create the tables
    # db.create_tables([BskySession, Feed, Fetch, Article, ArticlePost, ArticleMeta])
