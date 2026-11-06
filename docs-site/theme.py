"""Prepare the homepage theme for self-contained documentation pages."""
from pathlib import Path
import re
import shutil
import json
from quality import registry


def install_theme(destination):
    theme = Path(__file__).parent
    homepage = (theme.parent / 'index.html').read_text()
    styles = re.findall(r'<style[^>]*>(.*?)</style>', homepage, re.DOTALL)
    if not styles:
        raise ValueError('the family homepage must provide its shared theme')
    (destination / '_layouts').mkdir(parents=True, exist_ok=True)
    (destination / '_includes').mkdir(exist_ok=True)
    (destination / 'assets').mkdir(exist_ok=True)
    (destination / '_data').mkdir(exist_ok=True)
    quality = registry()
    (destination / '_data/purifier_quality.json').write_text(json.dumps(quality['projects'], indent=2) + '\n')
    (destination / 'quality.json').write_text(json.dumps(quality, indent=2) + '\n')
    shutil.copyfile(theme / 'layout.html', destination / '_layouts/default.html')
    (destination / '_includes/base.css').write_text('\n'.join(styles))
    for asset in ('docs.css', 'docs.js'):
        shutil.copyfile(theme / asset, destination / '_includes' / asset)
        # Retain the asset paths used by consumers of earlier shared layouts.
        shutil.copyfile(theme / asset, destination / 'assets' / asset)
    shutil.copyfile(theme.parent / 'robots.txt', destination / 'robots.txt')
