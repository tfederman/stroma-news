import os
import logging
import sys


handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)

log = logging.getLogger()
log.setLevel(os.environ.get("LOGLEVEL", "INFO").upper())
log.addHandler(handler)


try:
    AUTH_USERNAME = os.environ["BSKY_AUTH_USERNAME"]
    AUTH_PASSWORD = os.environ["BSKY_AUTH_PASSWORD"]
except KeyError:
    log.critical("bsky credentials must be set in BSKY_AUTH_USERNAME and BSKY_AUTH_PASSWORD environment variables")
    raise


QUEUE_NAME_FETCH = "fetch"
QUEUE_NAME_POST  = "post"
QUEUE_NAME_MISC  = "misc"
