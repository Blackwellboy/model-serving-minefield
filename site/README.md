# Pages site

`site/build_site.py` turns the generated registry
(`dist/MINEFIELD_REGISTRY.json`) and the offline search UI in `web/` into a
static site: the search page plus one page per trap at `/trap/<id>/`, a
sitemap and robots.txt. Each trap page is a summary that links back to the
canonical entry file.

```bash
python3 site/build_site.py --out _site
python3 -m http.server -d _site 8000   # preview locally
```

Publishing is manual. `.github/workflows/pages.yml` runs only when started
from the Actions tab, and only does anything once GitHub Pages is enabled for
this repository with "GitHub Actions" as the source (Settings → Pages). It
builds from the default branch and deploys to
`https://blackwellboy.github.io/model-serving-minefield/`.
