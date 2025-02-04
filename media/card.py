from datetime import datetime, timezone

import requests

from settings import log
from utils.string import html_to_text
from database.models import ArticleMetaCardy


def get_post(session, article):

    article.title = html_to_text(article.title)
    embed, cardy_lookup = get_link_card_embed(session, article)

    text = []

    if article.feed_fetch.feed.title:
        text.append(f'Feed: "{article.feed_fetch.feed.title}"')

    if article.author:
        article.author = article.author.replace("(noreply@blogger.com)", "").strip()
        if "unknown" in article.author.lower():
            article.author = ""
        article.author = html_to_text(article.author)

    timestamp_format = "%A, %B %-d, %Y"

    if article.author and article.published_parsed:
        text.append(f'By: {article.author} on {article.published_parsed.strftime(timestamp_format)}')
    elif article.author and not article.published_parsed:
        text.append(f'By: {article.author}')
    elif article.published_parsed and not article.author:
        text.append(f'Published on {article.published_parsed.strftime(timestamp_format)}')

    post = {
        "$type": "app.bsky.feed.post",
        "text": "\n".join(text),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "embed": embed,
    }

    return post, cardy_lookup


def get_cardy_data(url):
    try:
        r = requests.get(f"https://cardyb.bsky.app/v1/extract?url={url}")
        assert r.status_code == 200, f"HTTP error getting cardy data: {r.status_code} - {r.text}"
        return r.json()
    except Exception as e:
        log.warning(f"Error fetching cardy data: {e.__class__.__name__} - {e}")
        return {}


def get_link_card_embed(session, article):

    try:
        img_url = article.articlemeta_set[0].og_image or article.articlemeta_set[0].twitter_image
        description = article.articlemeta_set[0].og_description or article.articlemeta_set[0].twitter_description
    except:
        img_url = None
        description = None

    cardy_lookup = False

    if not img_url or not description:

        article_meta_cardy, created = ArticleMetaCardy.get_or_create(article=article)

        if not created:
            img_url = article_meta_cardy.image
            description = article_meta_cardy.description
        else:
            cardy_data = get_cardy_data(article.link)
            cardy_lookup = True
            img_url = cardy_data.get("image")
            description = cardy_data.get("description")

            if cardy_data:
                article_meta_cardy.title = cardy_data.get("title")
                article_meta_cardy.description = description
                article_meta_cardy.image = img_url
                article_meta_cardy.save()

    if not description:
        description = html_to_text(article.summary)

    card = {"uri": article.link, "title": article.title, "description": description}

    if img_url:
        try:
            mimetype = get_mimetype(img_url)
            r = requests.get(img_url)
            r.raise_for_status()
            assert len(r.content) <= 999424, f"thumbnail image too big: ({len(r.content)}) {img_url} - {article.link}"
            upload_response = session.upload_file(r.content, mimetype)
            card["thumb"] = {
                '$type': 'blob', 
                'ref': {'$link': getattr(upload_response.blob.ref, '$link')}, 
                'mimeType': upload_response.blob.mimeType, 
                'size': upload_response.blob.size,
            }
        except Exception as e:
            log.warning(f"can't fetch image: {e.__class__.__name__} - {e}")

    return {
        "$type": "app.bsky.embed.external",
        "external": card,
    }, cardy_lookup

def get_mimetype(url):

    suffix = url.split(".")[-1].lower()
    mimetype = "application/octet-stream"

    if suffix in ["png"]:
        mimetype = "image/png"
    elif suffix in ["jpeg", "jpg"]:
        mimetype = "image/jpeg"
    elif suffix in ["webp"]:
        mimetype = "image/webp"

    return mimetype
