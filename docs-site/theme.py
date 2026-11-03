"""Prepare the homepage theme for self-contained documentation pages."""
from pathlib import Path
import re
import shutil


def install_theme(destination):
    theme = Path(__file__).parent
    homepage = (theme.parent / 'index.html').read_text()
    styles = re.findall(r'<style[^>]*>(.*?)</style>', homepage, re.DOTALL)
    if not styles:
        raise ValueError('the family homepage must provide its shared theme')
    (destination / '_layouts').mkdir(parents=True, exist_ok=True)
    (destination / '_includes').mkdir(exist_ok=True)
    (destination / 'assets').mkdir(exist_ok=True)
    shutil.copyfile(theme / 'layout.html', destination / '_layouts/default.html')
    (destination / '_includes/base.css').write_text('\n'.join(styles))
    for asset in ('docs.css', 'docs.js'):
        shutil.copyfile(theme / asset, destination / '_includes' / asset)
        # Retain the asset paths used by consumers of earlier shared layouts.
        shutil.copyfile(theme / asset, destination / 'assets' / asset)
