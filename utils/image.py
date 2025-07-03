import urllib
from urllib.parse import urlparse

import requests

from settings import log
from utils.strutil import is_likely_binary
from utils.httputil import get_http_headers, ACCEPT_TYPE_DEFAULT, ACCEPT_TYPE_IMAGES


def get_http_image(url, accept_type=ACCEPT_TYPE_DEFAULT):

    r = requests.get(url, headers=get_http_headers(accept_type))

    if url.startswith("https://cardyb.bsky.app/v1/image?url=") and r.status_code == 400:
        target_url = url.replace("https://cardyb.bsky.app/v1/image?url=", "")
        target_url = urllib.parse.unquote(target_url)
        log.warning(f'cardy returned 400 for image "{url}", trying "{target_url}"')
        return get_http_image(target_url)

    r.raise_for_status()

    mimetype = r.headers.get('Content-Type')
    if not mimetype:
        mimetype = get_mimetype(url)
        log.warning(f"missing Content-Type header, falling back to {mimetype} ({url})")

    if accept_type == ACCEPT_TYPE_DEFAULT and not is_likely_binary(r.content):
        return get_http_image(url, accept_type=ACCEPT_TYPE_IMAGES)
    elif accept_type == ACCEPT_TYPE_IMAGES and not is_likely_binary(r.content):
        raise Exception(f"image for does not seem to be binary data (after retry) - {url}")

    return r.content, mimetype


def get_mimetype(url):

    p = urlparse(url)
    extension = p.path.split(".")[-1].lower()
    mimetype = "application/octet-stream"

    if extension == "jpg":
        extension = "jpeg"

    if extension in "png,jpeg,webp,avif,gif".split(","):
        mimetype = f"image/{extension}"

    return mimetype


def is_image_content_type(s):
    return s and s.startswith("image/")
