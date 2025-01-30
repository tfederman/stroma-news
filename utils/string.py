from bs4 import BeautifulSoup


def html_to_text(s):

    if not "<" in s:
        return s

    soup = BeautifulSoup(s, 'html.parser')
    return soup.get_text(strip=False)
