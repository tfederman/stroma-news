import urllib

import requests

from settings import log
from utils.strutil import is_likely_binary
from utils.http import get_http_headers, ACCEPT_TYPE_DEFAULT, ACCEPT_TYPE_IMAGES


def get_http_image(url, accept_type=ACCEPT_TYPE_DEFAULT):

    mimetype = get_mimetype(url)
    r = requests.get(url, headers=get_http_headers(accept_type))

    if url.startswith("https://cardyb.bsky.app/v1/image?url=") and r.status_code == 400:
        target_url = url.replace("https://cardyb.bsky.app/v1/image?url=", "")
        target_url = urllib.parse.unquote(target_url)
        log.warning(f'cardy returned 400 for image "{url}", trying "{target_url}"')
        return get_http_image(target_url)

    r.raise_for_status()

    if accept_type == ACCEPT_TYPE_DEFAULT and not is_likely_binary(r.content):
        return get_http_image(url, accept_type=ACCEPT_TYPE_IMAGES)
    elif accept_type == ACCEPT_TYPE_IMAGES and not is_likely_binary(r.content):
        raise Exception(f"image for does not seem to be binary data (after retry) - {url}")

    return r.content, mimetype


def get_mimetype(url):

    suffix = url.split(".")[-1].lower().split("?")[0]
    mimetype = "application/octet-stream"

    if suffix in ["png"]:
        mimetype = "image/png"
    elif suffix in ["jpeg", "jpg"]:
        mimetype = "image/jpeg"
    elif suffix in ["webp"]:
        mimetype = "image/webp"
    elif suffix in ["gif"]:
        mimetype = "image/gif"

    return mimetype


def is_image_content_type(s):
    return s and s.startswith("image/")
