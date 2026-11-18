# Shaoxing-No.1-High-School-LaTeX-Beamer-Template project website
[简体中文](site/index.html) · [English](site/en/index.html)

Open either HTML file in a browser, or run the following from `project-website/`:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory site
```

Visit <http://127.0.0.1:8765/>. Change `project.json` for identity and destinations,
and edit `locales/zh-CN.json` and `locales/en.json` together for visitor copy.

```sh
python3 scripts/render_site.py
python3 scripts/check.py
```

The eight committed HTML pages work without JavaScript. JavaScript adds the mobile
menu and remembers the appearance choice. CI also tests keyboard navigation, all
eight routes, theme selection and responsive layout using Chrome and ChromeDriver.
See `NOTICE` and `LICENSE.template` for the template provenance.
