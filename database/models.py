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


class BskyAPIResponseError(BaseModel):

    timestamp = DateTimeField(default=datetime.now)
    api_host = CharField()
    endpoint = CharField()
    params = CharField(null=True)
    method = CharField()
    headers = CharField(null=True)
    auth_method = CharField()
    http_status_code = IntegerField(null=True)
    exception_class = CharField(null=True)
    exception_text = CharField(null=True)
    response_text = CharField(null=True)

    class Meta:
        table_name = "bsky_api_response_error"


class BskyUserProfile(BaseModel):
    did = CharField(unique=True)
    handle = CharField(unique=True)
    display_name = CharField(null=True)
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

            try:
                response = session.get_profile(actor)
            except Exception as e:
                print(f"+++ EXCEPTION in BskyUserProfile.get_or_create_from_api: {e}")
                return None

            user, _ = BskyUserProfile.get_or_create(did=response.did, defaults={
                "handle": response.handle,
                "display_name": getattr(response, "displayName", None),
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


class UserFeedSubscription(BaseModel):
    user = ForeignKeyField(BskyUserProfile)
    feed = ForeignKeyField(Feed)
    active = BooleanField(default=True)

    class Meta:
        table_name = "user_feed_subscription"


class UserTextFilter(BaseModel):
    user = ForeignKeyField(BskyUserProfile)
    text = CharField()

    class Meta:
        table_name = "user_text_filter"

"""
users = list(BskyUserProfile.select())
feeds = list(Feed.select().where(Feed.active==True))

import random

for user in users:
    for n in range(random.randint(1,20)):
        UserFeedSubscription.create(user=user, feed=random.choice(feeds))

c = Counter()
for user in users:
    articles = Article.select() \
                .join(FeedFetch) \
                .join(Feed) \
                .join(UserFeedSubscription) \
                .join(ArticlePost, on=(Article.id==ArticlePost.article_id)) \
                .where(UserFeedSubscription.user==user) \
                .where(Feed.active==True) \
                .where(UserFeedSubscription.active==True) \
                .order_by(Article.published_parsed.desc())
    c.update([len(articles)])

"""
