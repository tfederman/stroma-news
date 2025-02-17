from collections import Counter

from bs4 import BeautifulSoup

COMMON_TEXT_CHARS = set(range(32, 127)).union(set(ord(c) for c in '\n\r\t')).union({226,128,147,148,145,146})

def html_to_text(s):

    if not s or not "<" in s:
        return s

    soup = BeautifulSoup(s, 'html.parser')
    return soup.get_text(strip=False)

def is_likely_binary(data):
    c = Counter(char in COMMON_TEXT_CHARS for char in data)
    return c[False] / len(data) > 0.10
