# Project documentation sites

`prepare.py` turns a purifier's README into Jekyll source using the shared
layout and stylesheet here. Each project pins this repository's commit in
its Pages workflow so theme updates remain reviewable and reproducible.

```sh
python3 docs-site/prepare.py --repository nix-purifiers/lein-purifier \
  --readme /path/to/lein-purifier/README.md --output /tmp/pages-source
jekyll build --source /tmp/pages-source --destination /tmp/pages-site
```

The theme follows the operating system's light/dark preference. Navigation
links keep the same font metrics during hover, focus and activation.
Source-file links in the README become GitHub links; headings and external
links keep their original destinations.

sbt's release workflow merges these documentation files with its Maven
repository before deploying one combined Pages artifact. Never deploy a
documentation-only artifact over sbt's published packages.

Code examples use source line breaks where possible and visual wrapping on
narrow screens. `docs.js` adds copy buttons that copy the underlying text,
including shell continuations. If clipboard access is denied, it selects
the example for manual copying. Code remains readable with JavaScript off.
