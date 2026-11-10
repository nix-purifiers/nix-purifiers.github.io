"""Proposed CENTRAL native-publisher helper: aliases only, no documentation data."""
import argparse
from html import escape
import json
from pathlib import Path
import re


def write_entries(repository, site):
    if not re.fullmatch(r'nix-purifiers/[a-z0-9][a-z0-9-]*(?:-purifier)?', repository):
        raise ValueError('invalid canonical repository')
    name = repository.split('/')[1]
    site.mkdir(parents=True, exist_ok=True)
    for page in ['index.html', 'reference.html', 'features.html']:
        target = 'https://nix-purifiers.github.io/projects/' + name + '/' + ('' if page == 'index.html' else page)
        html = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                '<title>Documentation moved</title><link rel="canonical" href="' + escape(target, quote=True) + '">'
                '<meta http-equiv="refresh" content="0;url=' + escape(target, quote=True) + '"></head>'
                '<body><p><a href="' + escape(target, quote=True) + '">Continue to the documentation</a></p>'
                '<script>location.replace(' + json.dumps(target) + '+location.search+location.hash);</script>'
                '</body></html>\n')
        (site / page).write_text(html)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--site', type=Path, required=True)
    args = parser.parse_args()
    write_entries(args.repository, args.site)
