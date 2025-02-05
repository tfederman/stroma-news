import json
import subprocess
from itertools import groupby

from settings import log
from database.models import Feed, Article, FeedFetch, BskyUserProfile, ArticlePost, UserFeedSubscription

DID_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyz'


def get_feed_json(article_posts, cursor="c"):
    posts = [{"post": ap.uri} for ap in article_posts]
    return json.dumps({"cursor": cursor, "feed": posts})


if __name__ == "__main__":

    # save this optimization for later if needed, reduce number of files to one per letter in alphabet
    # files = {c:open(f"feed-json/users-{c}.json", "w") for c in DID_ALPHABET}

    subscriptions = BskyUserProfile.select(BskyUserProfile.did, Feed.id) \
                        .join(UserFeedSubscription) \
                        .join(Feed) \
                        .where(UserFeedSubscription.active==True) \
                        .where(Feed.active==True) \
                        .order_by(UserFeedSubscription.user) \
                        .namedtuples()

    updated_files = 0

    for user, feeds in groupby(subscriptions, lambda row: row.did):
        article_posts = ArticlePost.select(ArticlePost.uri) \
                            .join(Article) \
                            .join(FeedFetch) \
                            .where(FeedFetch.feed_id << [f.id for f in feeds]) \
                            .where(ArticlePost.uri.is_null(False)) \
                            .order_by(Article.published_parsed.desc()) \
                            .limit(48)

        did_minus_prefix = user.replace("did:plc:", "")
        filename = f"feed-json/{did_minus_prefix}.json"

        feed_json = get_feed_json(article_posts)
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
        # client.put_object(Body=feed_json, Bucket="stroma-news", Key=f"feed-json/{user}.json")


    log.info(f"{updated_files} files updated")
    log.info("syncing files to s3...")
    cmd = ["aws", "--quiet", "s3", "sync", "./feed-json/", "s3://stroma-news/feed-json/"]
    subprocess.check_call(cmd)
