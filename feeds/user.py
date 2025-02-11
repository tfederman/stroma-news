import json

from settings import log, LOCAL_FEED_PATH
from database.models import Feed, FeedFetch, Article, UserFeedSubscription, BskyUserProfile, ArticlePost


def apply_filters(posts):
    terms = ["trump","musk"]
    log.info(f"feed length before filters: {len(posts)}")
    posts = [p for p in posts if not any(t in f"{p.article.title or ''} {p.article.summary or ''}".lower() for t in terms)]
    log.info(f"feed length after filters: {len(posts)}")
    return posts


def build_user_feed(user):

    subscriptions = BskyUserProfile \
                        .select(Feed.id, Feed.active, Feed.title, Feed.site_href, Feed.uri) \
                        .join(UserFeedSubscription) \
                        .join(Feed) \
                        .where(UserFeedSubscription.user==user) \
                        .where(UserFeedSubscription.active==True) \
                        .order_by(UserFeedSubscription.user) \
                        .namedtuples()

    article_posts = ArticlePost.select(ArticlePost.id, ArticlePost.uri, Article.title, Article.summary) \
                        .join(Article) \
                        .join(FeedFetch) \
                        .where(FeedFetch.feed_id << [sub.id for sub in subscriptions]) \
                        .where(ArticlePost.uri.is_null(False)) \
                        .order_by(ArticlePost.id.desc()) \
                        .limit(512)

    subscriptions = list(subscriptions)
    metadata = {"handle": user.handle,
                "subscriptions": [{"uri": sub.uri, "active": sub.active, "site_href": sub.site_href, "title": sub.title} for sub in subscriptions]}

    did_minus_prefix = user.did.replace("did:plc:", "")
    filename = f"{LOCAL_FEED_PATH}/{did_minus_prefix}.json"

    article_posts = apply_filters(article_posts)
    posts = [{"cursor": ap.id, "post": ap.uri} for ap in article_posts]
    feed_json = json.dumps({"feed": posts, "metadata": metadata})
    try:
        feed_json_prior = open(filename).read()
    except FileNotFoundError:
        feed_json_prior = ""

    # don't rewrite unchanged files because the changed timestamp will slow
    # down s3 sync as the unchanged content will get be re-uploaded
    if feed_json == feed_json_prior:
        return False

    with open(filename, "w") as f:
        f.write(feed_json)
        return True
