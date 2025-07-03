from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from settings import log
from database.models import Article, ArticleMeta
from utils.strutil import html_to_text, is_likely_binary
from utils.httputil import get_http_headers
from utils.image import is_image_content_type

def get_article_meta(article_id):

    article = Article.get(Article.id == article_id)
    article_meta, _ = ArticleMeta.get_or_create(article=article)

    try:
        r = requests.get(article.link, headers=get_http_headers(), timeout=8)
        article_meta.status = r.status_code
        assert r.status_code == 200, f"r.status_code in get_article_meta: {r.status_code}"
        article_meta.content_language = r.headers.get("Content-Language")
        content_type = r.headers.get("Content-Type")
        if is_image_content_type(content_type):
            raise Exception(f"bad content type for article in get_article_meta: {content_type}")
        bs = BeautifulSoup(r.text, 'html.parser')

        tags = {
            "og_title": lambda bs: bs.find("meta", property="og:title").attrs["content"],
            "og_url":   lambda bs: bs.find("meta", property="og:url").attrs["content"],
            "og_image": lambda bs: bs.find("meta", property="og:image").attrs["content"],
            "og_locale":lambda bs: bs.find("meta", property="og:locale").attrs["content"],
            "og_description":      lambda bs: bs.find("meta", property="og:description").attrs["content"],
            "twitter_image":       lambda bs: bs.find_all("meta", attrs={"name":"twitter:image"})[0].attrs["content"],
            "twitter_description": lambda bs: bs.find_all("meta", attrs={"name":"twitter:description"})[0].attrs["content"],
            "html_attr_lang":      lambda bs: bs.find("html").attrs.get("lang"),
            "canonical_link":      lambda bs: bs.find_all("link", rel="canonical")[0].attrs["href"],
        }

        for k,v in tags.items():
            try:
                val = v(bs)
                if "description" in k:
                    val = html_to_text(val)[:4*1024]
                setattr(article_meta, k, val.strip().replace("\x00", ""))
            except Exception as e:
                pass

        fix_image_links(article, article_meta, "og_image")
        fix_image_links(article, article_meta, "twitter_image")

        for tag in bs.find_all("link"):
            _type = tag.attrs.get("type") or ""
            href = tag.attrs.get("href")
            if (
                _type.startswith("application/rss") or _type.startswith("application/atom")
            ) and href:
                article_meta.rss_url = href

    except Exception as e:
        article_meta.exception = str(e)
        try:
            if not is_likely_binary(r.content) and not "bad content type" in article_meta.exception:
                article_meta.text = r.text[:2048]
        except:
            pass

    article_meta.save()


def fix_image_links(article, article_meta, property_name):
    img = getattr(article_meta, property_name, None)
    if not img or not img.strip() or img.startswith("http"):
        return

    if img.startswith("data:"):
        log.warning(f"article {article.id} image looks like base64 encoded data: {img[:48]}")
        setattr(article_meta, property_name, None)
        return

    try:
        p_img = urlparse(img)
        p_art = urlparse(article.link)
    except Exception as e:
        log.warning(f"fix_image_links parse error for {article.link} ({article.id}) ({e}) ({img})")
        return

    # use either the scheme from the article url or both the scheme and netloc
    if not p_img.scheme and not p_img.netloc:
        p_img = p_img._replace(scheme=p_art.scheme)
        p_img = p_img._replace(netloc=p_art.netloc)
    elif not p_img.scheme and "." in p_img.netloc:
        p_img = p_img._replace(scheme=p_art.scheme)
    else:
        return

    log.info(f"changing bad {property_name} link ({article.id}) from {img} to {urlunparse(p_img)}")
    setattr(article_meta, property_name, urlunparse(p_img))
