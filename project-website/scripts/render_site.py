#!/usr/bin/env python3
"""Render the localized project website using Python's standard library only."""

import argparse
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "project-homepage.html"
ICONS = {
    "home": '<path d="m3 10 9-7 9 7v11h-6v-7H9v7H3z"/>',
    "trophy": '<path d="M8 3h8v6a4 4 0 0 1-8 0V3ZM8 5H4v3a4 4 0 0 0 4 4m8-7h4v3a4 4 0 0 1-4 4M12 13v5m-4 3h8m-8-3h8v3"/>',
    "layers": '<path d="m12 3 10 5-10 5L2 8l10-5Zm-9 10 9 5 9-5M3 18l9 5 9-5"/>',
    "book": '<path d="M5 3h15v18H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm0 14h15M7 7h9M7 11h6"/>',
    "code": '<path d="m7 5-6 7 6 7M17 5l6 7-6 7M14 2l-4 20"/>',
    "download": '<path d="M12 2v13m-5-5 5 5 5-5M3 15v6h18v-6"/>',
    "link": '<path d="m10 7 3-3a5 5 0 0 1 7 7l-3 3M14 17l-3 3a5 5 0 0 1-7-7l3-3m1 6 8-8"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>',
    "moon": '<path d="M20.5 14A9 9 0 0 1 10 3.5 9 9 0 1 0 20.5 14Z"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M12 17v4m-5 0h10"/>',
}


def _text(value, location, *, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f"{location} must be a non-empty string")
    if len(value) > 10000:
        raise ValueError(f"{location} is too long")
    return value


def _object(value, location):
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    return value


def _list(value, location, *, minimum=1, maximum=12):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{location} must contain {minimum}–{maximum} items")
    return value


def _url(value, location, *, image=False):
    value = _text(value, location)
    decoded = value
    for _ in range(4):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    if " " in value or any(ord(c) < 32 or ord(c) == 127 for c in decoded) or "\\" in decoded:
        raise ValueError(f"{location} contains unsafe URL characters")
    try:
        parsed = urlsplit(value)
        decoded_parsed = urlsplit(decoded)
        if parsed.scheme:
            if image or parsed.scheme != "https" or not parsed.hostname or " " in unquote(parsed.netloc) or parsed.username or parsed.password:
                raise ValueError(f"{location} must use HTTPS or a safe relative path")
            parsed.port
        elif parsed.netloc or decoded.startswith("//") or decoded_parsed.scheme or ":" in decoded:
            raise ValueError(f"{location} must use HTTPS or a safe relative path")
        elif ".." in decoded_parsed.path.split("/"):
            raise ValueError(f"{location} cannot escape the site directory")
        if image and (not parsed.path or parsed.path.startswith("/") or parsed.fragment or parsed.query):
            raise ValueError(f"{location} must be relative to the site directory")
    except (ValueError, UnicodeError) as error:
        raise ValueError(f"{location}: unsafe URL") from error
    return value


PAGES = {"home": "index.html", "features": "features.html", "download": "download.html", "community": "community.html"}
LINKS = ("repository", "download", "release", "documentation", "report_issue", "suggest_feature", "contribute", "license")
UI_KEYS = ("skip_link", "navigation", "open_navigation", "close_navigation", "language", "theme", "light", "dark", "system", "platforms", "github", "view_image", "feature_more", "download", "release_notes", "documentation", "source", "illustration")
LANGUAGE_TAG = r"[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*"


def _icon(value, location):
    if not isinstance(value, str) or value not in ICONS:
        raise ValueError(f"{location} must name a supported icon")


def _image(value, location):
    value = _object(value, location)
    _url(value.get("src"), f"{location}.src", image=True)
    if "dark_src" in value:
        _url(value["dark_src"], f"{location}.dark_src", image=True)
    for key in ("alt", "caption"):
        _text(value.get(key), f"{location}.{key}")


def validate_config(config: dict) -> None:
    """Validate common data and the safe, explicit locale output registry."""
    c = _object(config, "config")
    if c.get("schema_version") != 2:
        raise ValueError("schema_version must be 2; see docs/adoption.md for migration")
    _text(c.get("name"), "name")
    _text(c.get("release"), "release")
    _text(c.get("license_label"), "license_label")
    _text(c.get("copyright_notice"), "copyright_notice")
    if c.get("theme", "light") not in ("light", "dark", "system"):
        raise ValueError("theme must be light, dark or system")
    codes, directories = set(), set()
    for i, entry in enumerate(_list(c.get("locales"), "locales", maximum=12)):
        entry = _object(entry, f"locales[{i}]")
        code = _text(entry.get("code"), f"locales[{i}].code")
        if not re.fullmatch(LANGUAGE_TAG, code) or code.casefold() in codes:
            raise ValueError("Locale codes must be unique language tags")
        codes.add(code.casefold())
        _text(entry.get("label"), f"locales[{i}].label")
        directory = entry.get("directory")
        if not isinstance(directory, str) or (directory and not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-]{0,31}", directory)):
            raise ValueError("Locale directory must be empty or one safe directory name")
        if directory.casefold() in directories or directory.casefold() in ("assets", "work", "outputs") or re.fullmatch(r"(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])", directory):
            raise ValueError("Locale directories must be unique and cannot use reserved names")
        directories.add(directory.casefold())
        if (code == c.get("default_locale")) != (directory == ""):
            raise ValueError("Only the default locale must use the root directory")
    if c.get("default_locale") not in {item["code"] for item in c["locales"]}:
        raise ValueError("default_locale must be registered")
    links = _object(c.get("links"), "links")
    for key in LINKS:
        _url(links.get(key), f"links.{key}")
    for code, overrides in c.get("localized_links", {}).items():
        if code.casefold() not in codes or not isinstance(overrides, dict):
            raise ValueError("Invalid localized links")
        for key, value in overrides.items():
            if key not in LINKS:
                raise ValueError("Unexpected localized link")
            _url(value, f"localized_links.{code}.{key}")
    for i, platform in enumerate(_list(c.get("platforms", []), "platforms", minimum=0, maximum=8)):
        platform = _object(platform, f"platforms[{i}]")
        _text(platform.get("name"), f"platforms[{i}].name")
        _url(platform.get("href"), f"platforms[{i}].href")
        if platform.get("logo") is not None:
            _url(platform["logo"], f"platforms[{i}].logo", image=True)
        if not isinstance(platform.get("wordmark", False), bool):
            raise ValueError("platform.wordmark must be a boolean")
    capture = _object(c.get("preview", {}), "preview").get("image")
    if capture is not None:
        _url(_object(capture, "preview.image").get("src"), "preview.image.src", image=True)


def validate_locale(locale: dict, location="locale") -> None:
    """Validate translated content, including local artwork and accessible labels."""
    t = _object(locale, location)
    _text(_object(t.get("meta"), "meta").get("description"), "meta.description")
    for page in PAGES:
        data = _object(_object(t.get("pages"), "pages").get(page), f"pages.{page}")
        _text(data.get("title"), f"pages.{page}.title")
        if page != "home":
            _text(data.get("description"), f"pages.{page}.description")
        _text(_object(t.get("nav"), "nav").get(page), f"nav.{page}")
    ui = _object(t.get("ui"), "ui")
    for key in UI_KEYS:
        _text(ui.get(key), f"ui.{key}")
    hero = _object(t.get("hero"), "hero")
    for key in ("title", "description"):
        for i, text in enumerate(_list(hero.get(key), f"hero.{key}", maximum=4)):
            _text(text, f"hero.{key}[{i}]")
    for key in ("primary_action", "secondary_action"):
        _text(hero.get(key), f"hero.{key}")
    preview = _object(t.get("preview"), "preview")
    _text(preview.get("caption"), "preview.caption")
    if preview.get("image") is not None:
        for key in ("alt", "caption"):
            _text(_object(preview["image"], "preview.image").get(key), f"preview.image.{key}")
    else:
        for i, tab in enumerate(_list(preview.get("tabs"), "preview.tabs", maximum=5)):
            _text(_object(tab, "tab").get("label"), f"preview.tabs[{i}].label")
            _icon(tab.get("icon"), f"preview.tabs[{i}].icon")
        for i, item in enumerate(_list(preview.get("items"), "preview.items", maximum=4)):
            for key in ("title", "description"):
                _text(_object(item, "item").get(key), f"preview.items[{i}].{key}")
            _icon(item.get("icon"), f"preview.items[{i}].icon")
    features = _object(t.get("features"), "features")
    _text(features.get("title"), "features.title")
    for i, group in enumerate(_list(features.get("groups"), "features.groups", maximum=4)):
        group = _object(group, "feature")
        for key in ("title", "description", "detail"):
            _text(group.get(key), f"features.groups[{i}].{key}", empty=key == "detail")
        _icon(group.get("icon"), f"features.groups[{i}].icon")
        if group.get("image") is not None:
            _image(group["image"], f"features.groups[{i}].image")
        elif group.get("preview") is not None:
            mini = _object(group.get("preview"), "feature.preview")
            _text(mini.get("title"), "feature.preview.title")
            if mini.get("theme") not in ("light", "dark"):
                raise ValueError("feature preview theme must be light or dark")
            for row in _list(mini.get("rows"), "feature.preview.rows", maximum=5):
                _text(_object(row, "row").get("title"), "row.title")
                _text(row.get("meta"), "row.meta", empty=True)
    start = _object(t.get("getting_started"), "getting_started")
    _text(start.get("title"), "getting_started.title")
    for i, step in enumerate(_list(start.get("steps"), "getting_started.steps", maximum=2)):
        for key in ("title", "description"):
            _text(_object(step, "step").get(key), f"getting_started.steps[{i}].{key}")
        _icon(step.get("icon"), f"getting_started.steps[{i}].icon")
    community = _object(t.get("community"), "community")
    for key in ("title", "description"):
        _text(community.get(key), f"community.{key}")
    for i, link in enumerate(_list(community.get("links"), "community.links", minimum=3, maximum=3)):
        for key in ("label", "description"):
            _text(_object(link, "community link").get(key), f"community.links[{i}].{key}")
        _icon(link.get("icon"), f"community.links[{i}].icon")
    _text(_object(t.get("footer"), "footer").get("copyright"), "footer.copyright")
    _locale_shape(t)


def _locale_shape(value):
    if isinstance(value, dict):
        return {key: _locale_shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_locale_shape(item) for item in value]
    if not isinstance(value, str):
        raise ValueError("Translation leaves must be strings")
    return "string"


def load_locales(config, config_path=ROOT / "project.json") -> dict:
    validate_config(config)
    result = {}
    for entry in config["locales"]:
        path = Path(config_path).parent / "locales" / (entry["code"] + ".json")
        data = json.loads(path.read_text(encoding="utf-8"))
        validate_locale(data, entry["code"])
        result[entry["code"]] = data
    reference = _locale_shape(result[config["default_locale"]])
    for code, data in result.items():
        if _locale_shape(data) != reference:
            raise ValueError(f"Locale {code} must have the same translation keys and array shapes as the default locale")
    return result


def _escape(value):
    return html.escape(value, quote=True)


def _svg(name, class_name=""):
    return (f'<svg class="{class_name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def _tokens(value, config):
    if isinstance(value, str):
        values = {"project": config["name"], "release": config["release"], "copyright": config["copyright_notice"]}
        return re.sub(r"\{(project|release|copyright)\}", lambda m: values[m.group(1)], value)
    if isinstance(value, list):
        return [_tokens(item, config) for item in value]
    return {key: item if key in ("src", "dark_src", "icon") else _tokens(item, config)
            for key, item in value.items()}


def _path(entry, page):
    return (entry["directory"] + "/" if entry["directory"] else "") + PAGES[page]


def _href(value, prefix):
    if urlsplit(value).scheme or value.startswith(("#", "/")):
        return _escape(value)
    return _escape(prefix + value.removeprefix("./"))


def _product_preview(c, t, prefix):
    preview = t["preview"]
    capture = c.get("preview", {}).get("image")
    if capture is not None:
        data = _object(preview.get("image"), "preview.image translations")
        return (f'<a href="{_href(capture["src"], prefix)}"><img class="product-image" src="{_href(capture["src"], prefix)}" alt="{_escape(data["alt"])}"></a>'
                f'<figcaption>{_escape(data["caption"])}</figcaption>')
    steps = "".join(
        f'<li><a href="./download.html#instructions"><strong>{_escape(item["title"])}</strong>'
        f'<span>{_escape(item["description"])}</span></a></li>'
        for item in preview["items"]
    )
    return (f'<div class="guide-card"><h2>{_escape(preview["caption"])}</h2>'
            f'<ol>{steps}</ol></div>')


def _platforms(c, t, prefix):
    if not c.get("platforms"):
        return ""
    links = []
    for platform in c["platforms"]:
        if not platform.get("logo"):
            links.append(f'<a class="platform-link" href="{_href(platform["href"], prefix)}">'
                         f'<span>{_escape(platform["name"])}</span><span class="platform-arrow" aria-hidden="true">↗</span></a>')
            continue
        wordmark = platform.get("wordmark", False)
        label = "" if wordmark else f'<span>{_escape(platform["name"])}</span>'
        alt = _escape(platform["name"]) if wordmark else ""
        links.append(f'<a class="platform-link{" wordmark" if wordmark else ""}" href="{_href(platform["href"], prefix)}">'
                     f'<img src="{_href(platform["logo"], prefix)}" alt="{alt}" decoding="async">{label}</a>')
    return f'<nav class="platforms" aria-label="{_escape(t["ui"]["platforms"])}">{"".join(links)}</nav>'


def _feature(group, t, prefix):
    copy = (f'<div class="feature-copy"><h2>{_escape(group["title"])}</h2><p>{_escape(group["description"])}</p>'
            + (f'<p class="feature-detail">{_escape(group["detail"])}</p>' if group["detail"] else "") + '</div>')
    if group.get("image") is not None:
        image = group["image"]
        dark = (f'<img class="dark-image" src="{_href(image["dark_src"], prefix)}" alt="{_escape(image["alt"])}" '
                f'width="900" height="500" loading="lazy" decoding="async">') if image.get("dark_src") else ""
        return (f'<article class="feature feature-with-image">{copy}<figure class="feature-image">'
                f'<a href="{_href(image["src"], prefix)}" data-light-href="{_href(image["src"], prefix)}" '
                f'data-dark-href="{_href(image.get("dark_src", image["src"]), prefix)}" aria-label="{_escape(group["title"] + ": " + t["ui"]["view_image"])}">'
                f'<img class="{"light-image" if dark else ""}" src="{_href(image["src"], prefix)}" alt="{_escape(image["alt"])}" '
                f'width="900" height="500" loading="lazy" decoding="async">{dark}</a>'
                f'<figcaption>{_escape(image["caption"])}</figcaption></figure></article>')
    return f'<article class="feature guide-feature">{_svg(group["icon"])}{copy}</article>'


def _body(c, t, page, prefix):
    ui, links = t["ui"], c["links"]
    if page == "home":
        hero = t["hero"]
        teasers = "".join(f'<article class="feature-teaser {"teaser-code" if i % 2 == 0 else "teaser-training"}">'
                          f'<header>{_svg(group["icon"])}<h2>{_escape(group["title"])}</h2></header><p>{_escape(group["description"])}</p>'
                          f'<a class="feature-more" href="./features.html">{_escape(ui["feature_more"])} <span aria-hidden="true">→</span></a></article>'
                          for i, group in enumerate(t["features"]["groups"]))
        return (f'<section class="hero" aria-labelledby="hero-title"><div class="hero-copy"><h1 id="hero-title">'
                + '<br>'.join(_escape(line) for line in hero["title"]) + '</h1><div class="hero-description">'
                + ''.join(f'<p>{_escape(p)}</p>' for p in hero["description"]) + '</div>' + _platforms(c, t, prefix)
                + f'<div class="hero-actions"><a class="button button-primary" href="{_href(links["download"], prefix)}">{_escape(hero["primary_action"])}</a>'
                  f'<a class="button button-secondary" href="./features.html">{_escape(hero["secondary_action"])}</a></div>'
                  f'</div><figure class="product-preview">{_product_preview(c, t, prefix)}</figure></section>'
                  f'<section class="home-features section-rule" aria-label="{_escape(t["nav"]["features"])}"><div class="feature-teasers">{teasers}</div></section>')
    if page == "features":
        return (f'<header class="page-heading"><h1>{_escape(t["features"]["title"])}</h1><p>{_escape(t["pages"][page]["description"])}</p></header>'
                + _platforms(c, t, prefix) + '<div class="feature-groups">'
                + ''.join(_feature(group, t, prefix) for group in t["features"]["groups"]) + '</div>')
    if page == "download":
        steps = "".join(f'<a class="start-step" href="{_href(links["download" if i == 0 else "documentation"], prefix)}">'
                        f'<span class="step-icon">{_svg(step["icon"])}</span><span><strong>{_escape(step["title"])}</strong>'
                        f'<span>{_escape(step["description"])}</span></span></a>' for i, step in enumerate(t["getting_started"]["steps"]))
        return (f'<header class="page-heading"><h1>{_escape(t["getting_started"]["title"])}</h1><p>{_escape(t["pages"][page]["description"])}</p></header>'
                f'<section class="download-panel" aria-labelledby="download-version">{_svg("download")}<div><h2 id="download-version">{_escape(t["nav"]["download"])}</h2>'
                f'<div class="download-actions"><a class="button button-primary" href="{_href(links["download"], prefix)}">{_escape(ui["download"])}</a>'
                f'<a class="release-link" href="{_href(links["release"], prefix)}">{_escape(ui["release_notes"])} <span aria-hidden="true">↗</span></a></div></div></section>'
                f'<section class="getting-started" id="instructions"><h2>{_escape(t["nav"]["download"])}</h2><div class="start-steps">{steps}</div></section>'
                f'<a class="docs-link" href="{_href(links["documentation"], prefix)}">{_svg("book")}{_escape(ui["documentation"])} <span aria-hidden="true">↗</span></a>')
    rows = "".join(f'<a class="community-row" href="{_href(links[key], prefix)}">{_svg(item["icon"])}<span class="row-copy">'
                   f'<strong>{_escape(item["label"])}</strong><span>{_escape(item["description"])}</span></span><span class="arrow" aria-hidden="true">→</span></a>'
                   for item, key in zip(t["community"]["links"], ("report_issue", "suggest_feature", "contribute")))
    return (f'<header class="page-heading"><h1>{_escape(t["community"]["title"])}</h1><p>{_escape(t["community"]["description"])}</p></header>'
            f'<div class="community-rows">{rows}</div><a class="source-link" href="{_href(links["repository"], prefix)}">{_svg("code")}'
            f'{_escape(ui["source"])} <span aria-hidden="true">↗</span></a>')


def render(config: dict, locale=None, page="home", locale_code=None) -> str:
    """Render one fully static page using escaped translations and trusted routes."""
    validate_config(config)
    if page not in PAGES:
        raise ValueError("Unknown page")
    code = locale_code or config["default_locale"]
    entry = next((item for item in config["locales"] if item["code"] == code), None)
    if entry is None:
        raise ValueError("Unregistered locale")
    if locale is None:
        locale = load_locales(config)[code]
    validate_locale(locale, code)
    t = _tokens(locale, config)
    c = dict(config, links={**config["links"], **config.get("localized_links", {}).get(code, {})})
    ui = t["ui"]
    prefix = "../" if entry["directory"] else "./"
    nav = ''.join(f'<a href="./{filename}"' + (' aria-current="page"' if key == page else '') + f'>{_escape(t["nav"][key])}</a>' for key, filename in PAGES.items())
    language_links, alternates = [], []
    for target in c["locales"]:
        route = prefix + _path(target, page)
        current = ' aria-current="true"' if target["code"] == code else ''
        language_links.append(f'<a href="{route}" lang="{target["code"]}" hreflang="{target["code"]}"{current}>{_escape(target["label"])}</a>')
        alternates.append(f'<link rel="alternate" hreflang="{target["code"]}" href="{route}">')
    choices = ''.join(f'<button type="button" data-theme-choice="{mode}" aria-pressed="false">{_svg({"light": "sun", "dark": "moon", "system": "monitor"}[mode])}<span>{_escape(ui[mode])}</span></button>' for mode in ("light", "dark", "system"))
    values = {
        "LANGUAGE": code, "THEME": c.get("theme", "light"), "SITE_ROOT": prefix, "PAGE": page,
        "THEME_COLOR_LIGHT": "#18191b" if c.get("theme") == "dark" else "#ffffff",
        "THEME_COLOR_DARK": "#ffffff" if c.get("theme", "light") == "light" else "#18191b",
        "META_TITLE": _escape(t["pages"][page]["title"]), "META_DESCRIPTION": _escape(t["meta"]["description"] if page == "home" else t["pages"][page]["description"]),
        "ALTERNATES": ''.join(alternates), "NAME": _escape(c["name"]), "NAVIGATION": nav,
        "SKIP_LINK": _escape(ui["skip_link"]), "NAV_LABEL": _escape(ui["navigation"]),
        "OPEN_NAV": _escape(ui["open_navigation"]), "CLOSE_NAV": _escape(ui["close_navigation"]),
        "LANGUAGE_LABEL": _escape(ui["language"]), "LANGUAGE_NAME": _escape(entry["label"]), "LANGUAGE_LINKS": ''.join(language_links),
        "THEME_LABEL": _escape(ui["theme"]), "THEME_NAME": _escape(ui[c.get("theme", "light")]), "THEME_CHOICES": choices,
        "REPOSITORY_URL": _href(c["links"]["repository"], prefix), "GITHUB": _escape(ui["github"]),
        "CONTENT": _body(c, t, page, prefix), "COPYRIGHT": _escape(t["footer"]["copyright"]),
        "LICENSE_URL": _href(c["links"]["license"], prefix),
        "LICENSE_LABEL": _escape(t["ui"].get("license", c["license_label"])),
    }
    template = TEMPLATE.read_text(encoding="utf-8")
    def substitute(match):
        if match.group(1) not in values:
            raise ValueError(f"Unknown template placeholder {match.group(0)}")
        return values[match.group(1)]
    return re.sub(r"\{\{([A-Z_]+)\}\}", substitute, template)


def render_site(config, locales) -> dict:
    validate_config(config)
    codes = {entry["code"] for entry in config["locales"]}
    if set(locales) != codes:
        raise ValueError("Locale dictionaries must match the registry")
    reference = None
    for code, data in locales.items():
        validate_locale(data, code)
        shape = _locale_shape(data)
        if reference is not None and shape != reference:
            raise ValueError("Locale dictionaries must have matching translation keys and array shapes")
        reference = shape
    return {_path(entry, page): render(config, locales[entry["code"]], page, entry["code"])
            for entry in config["locales"] for page in PAGES}


def _retired_pages(output_dir, expected):
    marker = '<meta name="generator" content="Project website template">'
    retired = []
    for path in output_dir.rglob("*.html"):
        if path.is_file() and path.resolve().is_relative_to(output_dir.resolve()):
            name = path.relative_to(output_dir).as_posix()
            if name not in expected and marker in path.read_text(encoding="utf-8"):
                retired.append(name)
    return sorted(retired)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "project.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "site")
    parser.add_argument("--check", action="store_true", help="read-only check of all generated pages")
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        pages = render_site(config, load_locales(config, args.config))
        retired = _retired_pages(args.output_dir, pages)
        if args.check:
            outdated = [name for name, source in pages.items()
                        if not (args.output_dir / name).is_file() or (args.output_dir / name).read_text(encoding="utf-8") != source]
            if outdated or retired:
                if outdated:
                    print("Out of date: " + ", ".join(outdated), file=sys.stderr)
                if retired:
                    print("Retired generated pages require review: " + ", ".join(retired), file=sys.stderr)
                return 1
            print(f"All {len(pages)} project pages are current.")
        else:
            for name, source in pages.items():
                target = args.output_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source, encoding="utf-8", newline="\n")
            print(f"Rendered {len(pages)} project pages in {args.output_dir}")
            if retired:
                print("Retired generated pages retained for review: " + ", ".join(retired), file=sys.stderr)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"Cannot render site: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
