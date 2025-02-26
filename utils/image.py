import io
import math
import urllib

import requests
from PIL import Image

from settings import log
from utils.strutil import is_likely_binary
from utils.http import get_http_headers, ACCEPT_TYPE_DEFAULT, ACCEPT_TYPE_IMAGES

THUMB_SIZES = ((768, 768), (576, 576), (384, 384), (256, 256))


# "This file is too large. It is 980.06KB but the maximum size is 976.56KB"
MAX_ALLOWED_IMAGE_SIZE = math.floor(976.56 * 1024)


def resize_image(image_bytes):

    original_length = len(image_bytes)
    final_length = 0
    image = Image.open(io.BytesIO(image_bytes))

    for ts in THUMB_SIZES:
        image.thumbnail(ts)
        image_bytes_out = io.BytesIO()
        image.save(image_bytes_out, format=image.format)
        image_bytes_out = image_bytes_out.getvalue()
        final_length = len(image_bytes_out)
        if len(image_bytes_out) < MAX_ALLOWED_IMAGE_SIZE:
            return image_bytes_out

    raise Exception(
        f"failed to resize image to an appropriate size ({original_length} -> {final_length})"
    )


def ensure_resized_image(image_bytes):
    if len(image_bytes) > MAX_ALLOWED_IMAGE_SIZE:
        return resize_image(image_bytes)

    return image_bytes


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
