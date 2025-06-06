ACCEPT_TYPE_DEFAULT, ACCEPT_TYPE_IMAGES = range(2)

ACCEPT_DEFAULT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
)
ACCEPT_IMAGES = "image/jpeg,image/png,image/avif,image/gif,image/webp"

REQUESTS_HEADERS_COMMON = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Sec-GPC": "1",
}

REQUESTS_HEADERS = {
    ACCEPT_TYPE_DEFAULT: dict(REQUESTS_HEADERS_COMMON, Accept=ACCEPT_DEFAULT),
    ACCEPT_TYPE_IMAGES: dict(REQUESTS_HEADERS_COMMON, Accept=ACCEPT_IMAGES),
}


def get_http_headers(accept_type=ACCEPT_TYPE_DEFAULT):
    return REQUESTS_HEADERS[accept_type]
