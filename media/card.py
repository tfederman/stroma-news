from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


def get_post(session, feed_title, title, link, description, published_parsed, author):

    embed = get_link_card_embed(session, link, title, description)

    text = []

    if feed_title:
        text.append(f'Feed: "{feed_title}"')

    if author:
        author = author.replace("(noreply@blogger.com)", "").strip()
        if "unknown" in author.lower():
            author = ""

    if author and published_parsed:
        text.append(f'By: {author}, published: {published_parsed[:-3]}')
    elif author and not published_parsed:
        text.append(f'By: {author}')
    elif published_parsed and not author:
        text.append(f'Published: {published_parsed[:-3]}')

    post = {
        "$type": "app.bsky.feed.post",
        "text": "\n".join(text),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "embed": embed,
    }

    return post


def get_cardy_data(url):
    try:
        r = requests.get(f"https://cardyb.bsky.app/v1/extract?url={url}")
        image_url = r.json()["image"]
        assert r.status_code == 200, f"HTTP error getting cardy data: {r.status_code} - {r.text}"
        return r.json()
    except Exception as e:
        #print("error fetching image url from cardy:", e)
        return {}


def get_link_card_embed(session, url, title, description):

    cardy_data = get_cardy_data(url)

    img_url = cardy_data.get("image")
    cardy_description = cardy_data.get("description")
    if cardy_description:
        description = cardy_description
    else:
        soup = BeautifulSoup(description, 'html.parser')
        description = soup.get_text(strip=True)

    card = {"uri": url, "title": title, "description": description}

    if img_url:
        try:
            mimetype = get_mimetype(url)
            r = requests.get(img_url)
            r.raise_for_status()
            assert len(r.content) <= 999424, f"thumbnail image too big: ({len(r.content)}) {img_url} - {url}"
            upload_response = session.upload_file(r.content, mimetype)
            card["thumb"] = {
                '$type': 'blob', 
                'ref': {'$link': getattr(upload_response.blob.ref, '$link')}, 
                'mimeType': upload_response.blob.mimeType, 
                'size': upload_response.blob.size,
            }
        except Exception as e:
            print("can't fetch image:", e)

    return {
        "$type": "app.bsky.embed.external",
        "external": card,
    }

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
