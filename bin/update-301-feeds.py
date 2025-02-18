from peewee import fn

from database.models import Feed, FeedFetch


if __name__=="__main__":

    most_recent_fetch = (FeedFetch.select(FeedFetch.feed_id, fn.Max(FeedFetch.timestamp).alias("max_ts")).group_by(FeedFetch.feed_id))

    moved_feeds = Feed.select(Feed, FeedFetch.href, most_recent_fetch.c.max_ts) \
                .join(most_recent_fetch, on=(Feed.id==most_recent_fetch.c.feed_id)) \
                .join(FeedFetch, on=FeedFetch.timestamp==most_recent_fetch.c.max_ts) \
                .where(FeedFetch.status==301, Feed.active==True, Feed.uri!=FeedFetch.href) \
                .namedtuples()

    for feed in moved_feeds:

        if feed.uri == feed.href:
            print(f"Last fetch for feed #{feed.id} was a 301 but feed already points to the new location: {feed.uri}")
            continue

        feed_to_update = Feed.get(Feed.id==feed.id)
        integrity_check_feed = Feed.get_or_none(Feed.uri==feed.href)

        if integrity_check_feed and not feed_to_update.active:
            print(f"Updating feed #{feed_to_update.id} would cause a dupe but it's already set to inactive")

        elif integrity_check_feed:
            print(f"Setting feed #{feed.id} inactive because it would create a dupe with #{integrity_check_feed.id} on {integrity_check_feed.uri}")
            feed_to_update.active = False
            feed_to_update.save()

        else:
            print(f"Updating feed #{feed.id} ({feed.title})\n{feed.uri}\n{feed.href}\n")
            assert feed_to_update.uri == feed.uri and feed_to_update.uri != feed.href
            feed_to_update.uri = feed.href
            feed_to_update.save()
