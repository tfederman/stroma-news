import time
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse

import peewee
import requests
from bs4 import BeautifulSoup

from settings import log, TIMEZONE
from database.models import Article, ArticleMeta, ArticleMetaAlt
from utils.strutil import html_to_text
from utils.http import get_http_headers


def get_article_meta(article_id):

    article = Article.get(Article.id==article_id)

    TEMPORARY_EARLIEST_DATE = datetime.now(TIMEZONE) - timedelta(days=10)
    if article.published_parsed and article.published_parsed <= TEMPORARY_EARLIEST_DATE:
        log.warning(f"article {article.id} skipped in get_article_meta because it's too old: {article.published_parsed}")
        return

    article_meta, _ = ArticleMeta.get_or_create(article=article)

    try:
        r = requests.get(article.link, headers=get_http_headers(), timeout=8)
        article_meta.status = r.status_code
        assert r.status_code == 200, f"r.status_code in get_article_meta: {r.status_code}"
        bs = BeautifulSoup(r.text, 'html.parser')

        tags = {
            "og_title": lambda bs: bs.find("meta", property="og:title").attrs["content"],
            "og_url":   lambda bs: bs.find("meta", property="og:url").attrs["content"],
            "og_image": lambda bs: bs.find("meta", property="og:image").attrs["content"],
            "og_description":      lambda bs: bs.find("meta", property="og:description").attrs["content"],
            "twitter_image":       lambda bs: bs.find_all("meta", attrs={"name":"twitter:image"})[0].attrs["content"],
            "twitter_description": lambda bs: bs.find_all("meta", attrs={"name":"twitter:description"})[0].attrs["content"],
        }

        for k,v in tags.items():
            try:
                val = v(bs)
                if "description" in k:
                    val = html_to_text(val)
                setattr(article_meta, k, val)
            except Exception as e:
                pass

        fix_image_links(article, article_meta)

        for tag in bs.find_all("link"):
            _type = tag.attrs.get("type") or ""
            href = tag.attrs.get("href")
            if (_type.startswith("application/rss") or _type.startswith("application/atom")) and href:
                article_meta.rss_url = href

    except Exception as e:
        article_meta.exception = str(e)
        try:
            article_meta.text = r.text[:1024]
        except:
            pass

    article_meta.save()


def fix_image_links(article, article_meta):
    if not article_meta.og_image.startswith("http") or not article_meta.twitter_image.startswith("http"):
        try:
            p = urlparse(article.link)
        except:
            log.error(f"fix_image_links parse error for {article.link} ({article.id})")
            return
        prefix = f"{p.scheme}://{p.netloc}"
        if article_meta.og_image.startswith("/"):
            log.info(f"changing bad og_image link from {article_meta.og_image} to {prefix}{article_meta.og_image}")
            article_meta.og_image = f"{prefix}{article_meta.og_image}"
        elif not article_meta.og_image.startswith("http"):
            log.info(f"changing bad og_image link from {article_meta.og_image} to {prefix}/{article_meta.og_image}")
            article_meta.og_image = f"{prefix}/{article_meta.og_image}"

        if article_meta.twitter_image.startswith("/"):
            log.info(f"changing bad twitter_image link from {article_meta.twitter_image} to {prefix}{article_meta.twitter_image}")
            article_meta.twitter_image = f"{prefix}{article_meta.twitter_image}"
        elif not article_meta.twitter_image.startswith("http"):
            log.info(f"changing bad twitter_image link from {article_meta.twitter_image} to {prefix}/{article_meta.twitter_image}")
            article_meta.twitter_image = f"{prefix}/{article_meta.twitter_image}"


if __name__=="__main__":

    articles = Article.select().where(Article.link ** 'http%').order_by(peewee.fn.Random()).limit(20)
    for n,article in enumerate(articles):
        print(n, article.link)
        article_meta = get_article_meta(article.id)
        time.sleep(0.1)
