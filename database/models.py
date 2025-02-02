from datetime import datetime

from peewee import Model, IntegerField, ForeignKeyField, BooleanField, DecimalField
from playhouse.postgres_ext import DateTimeTZField as DateTimeField

from database import db
from database.fields import PostgreSQLCharField as CharField


class BaseModel(Model):
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
    added_at = DateTimeField(default=datetime.now)
    title = CharField(null=True)
    subtitle = CharField(null=True)
    site_href = CharField(null=True)
    image_url = CharField(null=True)
    next_fetch_at = DateTimeField(null=True)
    active = BooleanField(default=True)

    def reschedule_feed(self):
        latest_article = Article.select().order_by(published_parsed).limit(1).first()



class FeedFetch(BaseModel):
    feed = ForeignKeyField(Feed)
    version = CharField(null=True)
    timestamp = DateTimeField(default=datetime.now)
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
    http_duration = DecimalField(null=True)
    http_content_type = CharField(null=True)

    class Meta:
        table_name = "feed_fetch"


class Article(BaseModel):
    feed_fetch = ForeignKeyField(FeedFetch)
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
    timestamp = DateTimeField(default=datetime.now)
    og_title = CharField(null=True)
    og_url = CharField(null=True)
    og_image = CharField(null=True)
    twitter_image = CharField(null=True)
    status = IntegerField(null=True)
    exception = CharField(null=True)
    text = CharField(null=True)
    og_description = CharField(null=True)
    twitter_description = CharField(null=True)

    class Meta:
        table_name = "article_meta"


class ArticleMetaCardy(BaseModel):
    article = ForeignKeyField(Article, unique=True)
    title = CharField(null=True)
    image = CharField(null=True)
    description = CharField(null=True)
    timestamp = DateTimeField(default=datetime.now)
    # add exception/status?

    class Meta:
        table_name = "article_meta_cardy"


class ArticlePost(BaseModel):
    article = ForeignKeyField(Article, unique=True)
    posted_at = DateTimeField(default=datetime.now)
    post_id = CharField(null=True)
    exception = CharField(null=True)
    uri = CharField(null=True)

    class Meta:
        table_name = "article_post"


class BskyAPICursor(BaseModel):
    timestamp = DateTimeField(default=datetime.now)
    endpoint = CharField()
    cursor = CharField()

    class Meta:
        table_name = "bsky_api_cursor"


class BskyUserProfile(BaseModel):
    did = CharField(unique=True)
    handle = CharField(unique=True)
    display_name = CharField()
    viewer_muted = BooleanField()
    viewer_blocked = BooleanField()

    class Meta:
        table_name = "bsky_user_profile"

    @staticmethod
    def get_or_create_from_api(actor, session):
        try:
            if actor.startswith("did:"):
                return BskyUserProfile.get(BskyUserProfile.did==actor)
            else:
                return BskyUserProfile.get(BskyUserProfile.handle==actor)
        except BskyUserProfile.DoesNotExist:

            response = session.get_profile(actor)

            user, _ = BskyUserProfile.get_or_create(did=response.did, defaults={
                "handle": response.handle,
                "display_name": response.displayName,
                "viewer_muted": response.viewer.muted,
                "viewer_blocked": response.viewer.blockedBy,
            })

            return user


class ConvoMessage(BaseModel):
    message_id = CharField(unique=True)
    convo_id = CharField()
    sender_did = CharField()
    sender = ForeignKeyField(BskyUserProfile)
    text = CharField()
    sent_at = DateTimeField()
    received_at = DateTimeField(default=datetime.now)
    processed_at = DateTimeField(null=True)

    class Meta:
        table_name = "convo_message"
