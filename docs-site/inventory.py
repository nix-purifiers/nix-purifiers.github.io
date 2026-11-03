"""Require every purifier linked by the family homepage to have a content model."""
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit


class ProjectLinks(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.projects = set()
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        href = dict(attrs).get('href')
        if not href:
            return
        url = urlsplit(href)
        if url.netloc and url.netloc != 'nix-purifiers.github.io':
            return
        match = re.fullmatch(r'/([a-z0-9][a-z0-9-]*-purifier)/?', url.path)
        if match:
            self.projects.add(match[1])


def validate_coverage(catalog, homepage):
    linked = ProjectLinks(homepage).projects
    missing = linked - set(catalog)
    if missing:
        raise ValueError('Homepage links purifiers without structured documentation: ' + ', '.join(sorted(missing)))
    return linked
