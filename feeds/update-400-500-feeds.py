from peewee import fn

from database.models import Feed, FeedFetch


if __name__=="__main__":
    """Set inactive all feeds that have only ever had one status code, 400 or above, at least 4 times""" 

    # select feed_id, count(*), max(status)
    #   from feed_fetch 
    #   group by 1 
    #   having max(status)=min(status) 
    #       and max(status) >= 400 
    #       and count(*) > 4

    always_error_feeds = FeedFetch.select(FeedFetch.feed_id, fn.count(FeedFetch.id), fn.Max(FeedFetch.status)) \
                .group_by(FeedFetch.feed_id) \
                .having(fn.count(FeedFetch.id) > 4) \
                .having(fn.Max(FeedFetch.status) >= 400) \
                .having(fn.Max(FeedFetch.status)==fn.Min(FeedFetch.status)) \
                .tuples()

    for error_feed_id, count, status in always_error_feeds:

        feed_to_update = Feed.select().where(Feed.id==error_feed_id).where(Feed.active==True).first()

        if feed_to_update:
            print(f"Setting feed #{feed_to_update.id} inactive for status {status} ({count}) ({feed_to_update.uri})")
            feed_to_update.active = False
            feed_to_update.save()
