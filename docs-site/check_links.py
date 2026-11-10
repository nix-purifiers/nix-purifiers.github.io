"""Check rendered documentation URLs and required navigation before deployment."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links = []
        self.anchors = []
        self.anchor = None
        self.ids = set()
        self.canonical = []
        self.refreshes = []
        self.scripts = []
        self.in_script = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical.append(attrs.get('href'))
        if tag == 'meta' and attrs.get('http-equiv', '').lower() == 'refresh':
            self.refreshes.append(attrs.get('content'))
        if tag == 'script':
            self.in_script = True
            self.scripts.append('')
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'a' and 'name' in attrs:
            self.ids.add(attrs['name'])
        if tag == 'a' and attrs.get('href'):
            self.anchor = [attrs['href'], '']
            self.anchors.append(self.anchor)
        for key in ('href', 'src'):
            if attrs.get(key):
                self.links.append(attrs[key])

    def handle_data(self, text):
        if self.in_script:
            self.scripts[-1] += text
        if self.anchor is not None:
            self.anchor[1] += text

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_script = False
        if tag == 'a':
            self.anchor = None


def check(source, destination):
    config = json.loads((source / '_config.yml').read_text())
    root = destination.resolve()
    prefix = config.get('baseurl', '').rstrip('/')
    pages = {p.resolve(): Page(p.read_text()) for p in root.rglob('*.html')}
    failures = []
    navigation = 0
    for markdown in source.rglob('*.md'):
        canonical = re.search(r'^canonical_url: (".*")$', markdown.read_text(), re.M)
        if not canonical:
            continue
        url = json.loads(canonical[1])
        path = root / markdown.relative_to(source).with_suffix('.html')
        page = pages.get(path)
        script = 'location.replace(' + json.dumps(url).replace('<', '\\u003c') + '+location.search+location.hash);'
        if (page is None or page.canonical != [url] or page.refreshes != ['0;url=' + url]
                or script not in page.scripts):
            failures.append(f'{markdown.relative_to(source)}: legacy entry must automatically route to its canonical documentation, preserving query and fragment')
    for repository, matrix in config.get('feature_matrices', {}).items():
        doc_root = config.get('documentation_roots', {}).get(repository)
        folder = root if prefix else root / (doc_root.strip('/') if doc_root else repository.split('/')[1])
        expected = matrix if urlsplit(matrix).scheme else prefix + matrix
        for name in ('index.html', 'reference.html', 'features.html'):
            path = folder / name
            if path not in pages:
                failures.append(f'{repository}: missing {name}')
            elif expected not in pages[path].links:
                failures.append(f'{path.relative_to(root)}: missing matrix link {expected}')
            else:
                navigation += 1
        overview = pages.get(folder / 'index.html')
        if overview:
            guide = expected.replace('features.html', 'reference.html')
            guide_links = [(url, label) for url, label in overview.anchors
                           if url in {guide, 'reference.html', './reference.html'}]
            if len(guide_links) != 1 or guide_links[0][1].strip() != 'Full guide':
                failures.append(f'{repository}: expected exactly one Full guide navigation link')
    for path, page in pages.items():
        for link in page.links:
            url = urlsplit(link)
            if re.match(r'https://github\.com/[^/]+/[^/]+/blob/[^/]+/(?:reference|features)\.html(?:[?#]|$)', link):
                failures.append(f'{path.relative_to(root)}: generated page points into source repository: {link}')
                continue
            if url.scheme or url.netloc:
                if not prefix and link.startswith('https://nix-purifiers.github.io/projects/'):
                    resolved = root / url.path.lstrip('/')
                    if resolved.is_dir():
                        resolved /= 'index.html'
                    if not resolved.exists() or (url.fragment and resolved.resolve() in pages and unquote(url.fragment) not in pages[resolved.resolve()].ids):
                        failures.append(f'{path.relative_to(root)}: missing canonical documentation destination: {link}')
                continue
            target = unquote(url.path)
            if target.startswith('/'):
                if prefix and not target.startswith(prefix + '/'):
                    failures.append(f'{path.relative_to(root)}: link escapes project base URL: {link}')
                    continue
                target = target[len(prefix):] if prefix else target
                resolved = root / target.lstrip('/')
            else:
                resolved = path.parent / target if target else path
            resolved = resolved.resolve()
            if resolved.is_dir():
                resolved /= 'index.html'
            if not resolved.is_relative_to(root) or not resolved.exists():
                failures.append(f'{path.relative_to(root)}: missing local destination: {link}')
            elif url.fragment and resolved in pages and unquote(url.fragment) not in pages[resolved].ids:
                failures.append(f'{path.relative_to(root)}: missing fragment: {link}')
    if failures:
        raise ValueError('\n'.join(failures))
    return {'pages': len(pages), 'matrixLinks': navigation}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--site', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.source, args.site)))
