import time
import json

import peewee
import requests
from bs4 import BeautifulSoup

from database.models import *
from utils.strutil import html_to_text

headers = {
     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.3",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
     "Accept-Language": "en-US,en;q=0.5",
     "Accept-Encoding": "gzip, deflate, br",
     "DNT": "1",
     "Connection": "keep-alive",
     "Upgrade-Insecure-Requests": "1",
     "Sec-Fetch-Dest": "document",
     "Sec-Fetch-Mode": "navigate",
     "Sec-Fetch-Site": "same-origin",
     "Sec-Fetch-User": "?1",
     "Sec-GPC": "1"
}

def get_article_meta(article_id):

    article = Article.get(Article.id==article_id)
    article_meta, _ = ArticleMeta.get_or_create(article=article)

    try:
        r = requests.get(article.link, headers=headers, timeout=8)
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

    except Exception as e:
        article_meta.exception = str(e)
        try:
            article_meta.text = r.text[:1024]
        except:
            pass

    article_meta.save()


if __name__=="__main__":

    articles = Article.select().where(Article.link ** 'http%').order_by(peewee.fn.Random()).limit(20)
    for n,article in enumerate(articles):
        print(n, article.link)
        article_meta = get_article_meta(article.id)
        time.sleep(0.1)
