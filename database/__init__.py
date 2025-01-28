from datetime import datetime

import peewee

db = peewee.SqliteDatabase('stroma.db')


class BaseModel(peewee.Model):
    class Meta:
        database = db


class Feed(BaseModel):
    uri = peewee.CharField(unique=True)
    added_at = peewee.DateTimeField(default=datetime.utcnow)
    title = peewee.CharField(null=True)
    subtitle = peewee.CharField(null=True)
    site_href = peewee.CharField(null=True)


class Fetch(BaseModel):
    feed = peewee.ForeignKeyField(Feed)
    version = peewee.CharField(null=True)
    timestamp = peewee.DateTimeField(default=datetime.utcnow)
    status = peewee.IntegerField(null=True)
    updated = peewee.CharField(null=True)
    updated_parsed = peewee.DateTimeField(null=True)
    etag = peewee.CharField(null=True)
    modified = peewee.CharField(null=True)
    modified_parsed = peewee.DateTimeField(null=True)
    href = peewee.CharField(null=True)
    exception = peewee.CharField(null=True)
    etag_sent = peewee.CharField(null=True)
    modified_sent = peewee.CharField(null=True)
    http_duration = peewee.DecimalField(null=True)
    # alter table fetch add column http_duration decimal

class Article(BaseModel):
    fetch = peewee.ForeignKeyField(Fetch)
    link = peewee.CharField()
    title = peewee.CharField(null=True)
    entry_id = peewee.CharField(null=True, unique=True)
    summary = peewee.CharField(null=True)
    author = peewee.CharField(null=True)
    tags = peewee.CharField(null=True)
    updated = peewee.DateTimeField(null=True)
    updated_parsed = peewee.DateTimeField(null=True)
    published = peewee.CharField(null=True)
    published_parsed = peewee.DateTimeField(null=True)


class ArticlePost(BaseModel):
    article = peewee.ForeignKeyField(Article)
    posted_at = peewee.DateTimeField(default=datetime.utcnow)
    post_url = peewee.CharField(null=True)
    exception = peewee.CharField(null=True)


if __name__=="__main__":

    if db.is_closed():
        db.connect()
        db.create_tables([Feed, Fetch, Article, ArticlePost])
