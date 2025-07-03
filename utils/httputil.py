from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import feedparser

from settings import log

feedparser.USER_AGENT = "Longtail News RSS Reader Bot"

class InvalidContentType(Exception):
    pass

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

CONTENT_TYPES_HTML = [
    "text/html",
    "text/plain",
]

CONTENT_TYPES_RSS = [
    "application/atom+xml",
    "application/rss+xml",
    "application/rdf+xml",
    "application/x-rss+xml",
    "application/xml",
    "text/xml",
    "text/html",
    "text/plain",
    "xml",
]

COMMENT_FEED_TITLE_PREFIXES = [
    "comments on:",
    "comentarios en:",
    "commentaires sur",
    "reacties op:",
    "komente te:",
    "kommentare zu:",
    "comentários sobre:",
    "kommentarer til:",
    "kommentarer på:",
]

def get_http_headers(accept_type=ACCEPT_TYPE_DEFAULT):
    return REQUESTS_HEADERS[accept_type]


def get_url_contents(url, allowed_content_types):

    r = requests.get(url, headers=get_http_headers())

    if r.status_code != 200:
        return None, r.status_code

    content_type = r.headers.get("content-type") or ""
    content_type = content_type.split(";")[0].strip()

    if content_type not in allowed_content_types:
        raise InvalidContentType(content_type)

    return r.text, r.status_code


def get_rss_links(soup, url):

    def fix_relative_href(href):
        p = urlparse(url)
        if href.startswith("/"):
            return f"{p.scheme}://{p.netloc}{href}"
        elif not href.startswith("http"):
            return f"{p.scheme}://{p.netloc}/{href}"
        return href

    rss_links = []
    for tag in soup.find_all("link"):
        _type = tag.attrs.get("type") or ""
        href = tag.attrs.get("href")
        if (_type.startswith("application/rss") or _type.startswith("application/atom")) and href:
            rss_links.append(fix_relative_href(href).strip())

    rss_links.sort(key=lambda s: len(s))
    return rss_links


def get_rss_from_url(url):

    html, status_code = get_url_contents(url, CONTENT_TYPES_HTML)
    if status_code != 200:
        return None

    soup = BeautifulSoup(html, "lxml")
    rss_links = get_rss_links(soup, url)
    candidate_count = len(rss_links)
    rss_links = [fetch_rss_link(rss) for rss in rss_links]
    rss_links = [(rss, fp) for rss, fp in rss_links if fp]
    rss_links = [(rss, fp) for rss, fp in rss_links if allow_rss_link(rss, fp)]

    if len(rss_links) > 1:
        log.info(f"multiple rss feeds in url: {url}")
        for rss, fp in rss_links:
            log.info(f"    {rss}")
    elif len(rss_links) == 0 and candidate_count > 0:
        log.info(f"no rss feeds in url despite candidate count {candidate_count}: {url}")
    elif len(rss_links) == 0:
        log.info(f"no rss feeds in url: {url}")

    return rss_links[0][0] if rss_links else None


def fetch_rss_link(rss_link):
    try:
        fp = feedparser.parse(rss_link)
        return rss_link, fp
    except Exception as e:
        log.error(f"error fetching feed: {rss_link} - {e}")
        return rss_link, None


def allow_rss_link(rss, fp):
    try:
        status_code = getattr(fp, "status", 0)
        if status_code >= 400:
            log.error(f"filtering out feed for status code {status_code}: {rss}")
            return False

        if "/comments" in rss or any(p.lower() in fp.feed.title.lower() for p in COMMENT_FEED_TITLE_PREFIXES):
            log.error(f"filtering out feed for being a comment feed: {rss}")
            return False

        if not getattr(fp, "entries", []):
            log.error(f"filtering out feed for having no entries: {rss}")
            return False

        filter_str = ""
        for field in ["title", "subtitle", "uri"]:
            filter_str += (getattr(fp.feed, field, "") or "") + " "

        terms = [line.strip("\r\n") for line in open("ignore-feed-terms.txt")]
        if any(t in filter_str.lower() for t in terms):
            log.error(f"filtering out feed for its topic: {rss} - {filter_str}")
            return False

        return True
    except Exception as e:
        log.error(f"error testing feed: {rss} - {e}")
        return False
