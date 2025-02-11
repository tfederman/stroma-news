import json
import subprocess
from itertools import groupby

from settings import log, S3_BUCKET, S3_PREFIX, LOCAL_FEED_PATH
from database.models import Feed, Article, FeedFetch, BskyUserProfile, ArticlePost, UserFeedSubscription

DID_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyz'

def apply_filters(posts):
    terms = ["trump","musk"]
    posts = [p for p in posts if not any(t in f"{p.article.title or ''} {p.article.summary or ''}".lower() for t in terms)]
    return posts


if __name__ == "__main__":

    # save this optimization for later if needed, reduce number of files to one per letter in alphabet
    # files = {c:open(f"{LOCAL_FEED_PATH}/users-{c}.json", "w") for c in DID_ALPHABET}

    subscriptions = BskyUserProfile \
                        .select(BskyUserProfile.did, BskyUserProfile.handle, Feed.id, Feed.active, Feed.title, Feed.site_href, Feed.uri) \
                        .join(UserFeedSubscription) \
                        .join(Feed) \
                        .where(UserFeedSubscription.active==True) \
                        .order_by(UserFeedSubscription.user) \
                        .namedtuples()

    updated_files = 0

    for user, feeds in groupby(subscriptions, lambda row: row.did):

        feeds = list(feeds)
        metadata = {"handle": feeds[0].handle, "subscriptions": [{"uri": f.uri, "active": f.active, "site_href": f.site_href, "title": f.title} for f in feeds]}

        article_posts = ArticlePost.select(ArticlePost.id, ArticlePost.uri, Article.title, Article.summary) \
                            .join(Article) \
                            .join(FeedFetch) \
                            .where(FeedFetch.feed_id << [f.id for f in feeds if f.active]) \
                            .where(ArticlePost.uri.is_null(False)) \
                            .order_by(ArticlePost.id.desc()) \
                            .limit(512)

        did_minus_prefix = user.replace("did:plc:", "")
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
            continue

        with open(filename, "w") as f:
            f.write(feed_json)
            updated_files += 1

        # much too slow
        # client = boto3.client('s3')
        # client.put_object(Body=feed_json, Bucket=S3_BUCKET, Key=f"{S3_PREFIX}/{user}.json")


    log.info(f"{updated_files} files updated")
    log.info("syncing files to s3...")
    cmd = ["aws", "--quiet", "s3", "sync", f"{LOCAL_FEED_PATH}/", f"s3://{S3_BUCKET}/{S3_PREFIX}/"]
    subprocess.check_call(cmd)
