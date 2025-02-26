import os
import logging
import sys
from zoneinfo import ZoneInfo

from pysky import BskyClient

bsky = BskyClient()

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
handler.setFormatter(formatter)

log = logging.getLogger()
log.setLevel(os.environ.get("LOGLEVEL", "INFO").upper())
log.addHandler(handler)


try:
    AUTH_USERNAME = os.environ["BSKY_AUTH_USERNAME"]
    AUTH_PASSWORD = os.environ["BSKY_AUTH_PASSWORD"]
except KeyError:
    log.critical(
        "bsky credentials must be set in BSKY_AUTH_USERNAME and BSKY_AUTH_PASSWORD environment variables"
    )
    raise

try:
    S3_BUCKET = os.environ["S3_BUCKET"]
    S3_PREFIX = os.environ["S3_PREFIX"]
    LOCAL_FEED_PATH = os.environ["LOCAL_FEED_PATH"]
except KeyError:
    log.critical("filesystem environment variables not set")
    raise

QUEUE_NAME_FETCH = "fetch"
QUEUE_NAME_POST = "post"
QUEUE_NAME_MAIL = "mailbox"

TIMEZONE = ZoneInfo("America/New_York")
