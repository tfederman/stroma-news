import time
from datetime import datetime, timedelta

import redis

from settings import log, TIMEZONE
from database.models import ArticlePostRetry


MAX_SERVER_ERROR_COUNT = 10
SERVER_ERROR_RECENCY_SECONDS = 300
SERVER_ERROR_TIMESTAMPS_KEY = "server_error_timestamps"
SERVER_ERROR_TIMESTAMPS_MAX_LENGTH  = MAX_SERVER_ERROR_COUNT * 4
SERVER_ERROR_TIMESTAMPS_TRIM_LENGTH = MAX_SERVER_ERROR_COUNT * 2
SERVER_STRUGGLE_BEGIN_KEY = "struggle_begin_timestamp"
SERVER_STRUGGLE_BACKOFF_DURATION = 900


def log_server_error():
    r = redis.Redis()
    r.lpush(SERVER_ERROR_TIMESTAMPS_KEY, time.time())
    new_error_count = recent_error_count()
    log.warning(f"logging new 500 range server error (recent count: {new_error_count})")

    if new_error_count >= MAX_SERVER_ERROR_COUNT:
        log.warning(f"server is now flagged as struggling ({new_error_count},{MAX_SERVER_ERROR_COUNT})")
        r.set(SERVER_STRUGGLE_BEGIN_KEY, time.time())

    return new_error_count, new_error_count >= MAX_SERVER_ERROR_COUNT


def server_is_struggling():
    r = redis.Redis()
    struggle_begin_timestamp = r.get(SERVER_STRUGGLE_BEGIN_KEY)
    if struggle_begin_timestamp and time.time() - int(struggle_begin_timestamp) < SERVER_STRUGGLE_BACKOFF_DURATION:
        return True

    return False


def recent_error_count():

    r = redis.Redis()
    error_timestamps = r.lrange(SERVER_ERROR_TIMESTAMPS_KEY, 0, SERVER_ERROR_TIMESTAMPS_MAX_LENGTH+1)

    # reduce number of trims by trimming from [100] down to [50]
    # and then allow the list to get back up to [100] elements
    # rather than constantly trim from [100] down to [99]
    if len(error_timestamps) > SERVER_ERROR_TIMESTAMPS_MAX_LENGTH:
        r.ltrim(SERVER_ERROR_TIMESTAMPS_KEY, 0, SERVER_ERROR_TIMESTAMPS_TRIM_LENGTH)

    return sum(1 for t in error_timestamps if time.time() - float(t) < SERVER_ERROR_RECENCY_SECONDS)
