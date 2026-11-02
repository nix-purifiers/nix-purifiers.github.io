"""Prepare a purifier README for its GitHub Pages documentation site."""
import argparse
import json
from pathlib import Path
import re
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repository', required=True)
parser.add_argument('--readme', default='README.md', type=Path)
parser.add_argument('--output', default='.pages-source', type=Path)
args = parser.parse_args()
if not re.fullmatch(r'[\w.-]+/[\w.-]+', args.repository):
    parser.error('repository must be owner/name')
source = args.output
(source / '_layouts').mkdir(parents=True, exist_ok=True)
(source / 'assets').mkdir(exist_ok=True)
theme = Path(__file__).parent
shutil.copyfile(theme / 'layout.html', source / '_layouts/default.html')
shutil.copyfile(theme / 'docs.css', source / 'assets/docs.css')
text = args.readme.read_text()
# Keep source links useful outside GitHub, including images.
text = re.sub(r'\]\((?![a-zA-Z][\w+.-]*:|#|/)([^)]+)\)',
              lambda m: '](https://github.com/' + args.repository + '/blob/main/' + m[1] + ')', text)
(source / 'index.md').write_text('---\nlayout: default\n---\n\n' + text)
(source / '_config.yml').write_text(json.dumps({
    'title': args.repository.split('/')[1],
    'description': 'Native development with locked, Nix-resolved dependencies',
    'repository': args.repository,
    'url': 'https://nix-purifiers.github.io',
    'baseurl': '/' + args.repository.split('/')[1],
    'markdown': 'kramdown',
    'kramdown': {'input': 'GFM'},
}))
