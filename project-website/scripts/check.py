"""Check project website copies of the Tangyixiao schema-2 template, offline."""
import argparse
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

PAGES = {"home": "index.html", "features": "features.html",
         "download": "download.html", "community": "community.html"}
LANGUAGES = {"zh-CN": "", "en": "en"}
SAMPLE_COPY = (
    "OJ-NEXUS-v1.0.4.apk", "One place for competitive programming",
    "Keep your online judges together and focus on each problem.",
    "problem-workflow.svg", "problem-workflow-dark.svg", "training-review-en.svg",
    "github.com/tangyixiao/OJ-NEXUS/releases/download/v1.0.4/",
)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.language = ""
        self.ids = set()
        self.duplicates = set()
        self.refs = []
        self.nav = []
        self.languages = {}
        self.alternates = {}
        self.title = ""
        self.in_title = False
        self.in_main_nav = False
        self.in_anchor = False

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if "id" in attr:
            if attr["id"] in self.ids:
                self.duplicates.add(attr["id"])
            self.ids.add(attr["id"])
        if tag == "html":
            self.language = attr.get("lang")
        elif tag == "title":
            self.in_title = True
        elif tag == "nav":
            self.in_main_nav = attr.get("id") == "main-nav"
        elif tag == "a" and self.in_main_nav:
            self.in_anchor = True
            self.nav.append({"label": "", "href": attr.get("href", ""),
                             "current": attr.get("aria-current")})
        if tag == "a" and attr.get("hreflang"):
            self.languages[attr["hreflang"]] = attr.get("href", "")
        if tag == "link" and attr.get("rel") == "alternate":
            self.alternates[attr.get("hreflang")] = attr.get("href", "")
        for key in ("href", "src", "poster", "data-light-href", "data-dark-href"):
            if key in attr:
                self.refs.append((tag, key, attr[key]))
        for candidate in (attr.get("srcset") or "").split(","):
            if candidate.strip():
                self.refs.append((tag, "srcset", candidate.split()[0]))

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_anchor:
            self.nav[-1]["label"] += data

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "nav":
            self.in_main_nav = False
        elif tag == "a":
            self.in_anchor = False


def inspect(project, budget):
    project = project.resolve()
    site = project / "site"
    config = json.loads((project / "project.json").read_text())
    name = config["name"]
    errors = []
    check = subprocess.run([sys.executable, "-B", "scripts/render_site.py", "--check"],
                           cwd=project, text=True, capture_output=True, timeout=30)
    if check.returncode:
        errors.append(f"render --check: {(check.stderr or check.stdout).strip()[:1200]}")
    locales = {key: json.loads((project / "locales" / (key + ".json")).read_text())
               for key in LANGUAGES}
    parsed = {}
    refs = []
    titles = {page: set() for page in PAGES}
    sub = {"project": name, "release": config["release"], "copyright": config["copyright_notice"]}
    for language, directory in LANGUAGES.items():
        for role, filename in PAGES.items():
            path = site / directory / filename
            rel = path.relative_to(site)
            if not path.is_file():
                errors.append(f"Missing {rel}")
                continue
            html = path.read_text()
            page = Page()
            page.feed(html)
            parsed[path] = page
            if page.language != language:
                errors.append(f"{rel}: expected lang={language}")
            if page.duplicates:
                errors.append(f"{rel}: duplicate ids {sorted(page.duplicates)}")
            expected = locales[language]["pages"][role]["title"]
            expected = re.sub(r"\{(project|release|copyright)\}", lambda m: sub[m[1]], expected)
            if page.title != expected or not page.title.strip():
                errors.append(f"{rel}: incorrect translated title")
            titles[role].add(page.title)
            if len(page.nav) != len(PAGES):
                errors.append(f"{rel}: expected {len(PAGES)} nav entries")
            for (item, navfile), nav in zip(PAGES.items(), page.nav):
                if ((path.parent / nav["href"]).resolve() != (path.parent / navfile)
                        or nav["label"].strip() != locales[language]["nav"][item]
                        or (nav["current"] == "page") != (role == item)):
                    errors.append(f"{rel}: wrong {item} navigation link, label or current state")
            for code, langdir in LANGUAGES.items():
                for links in [page.languages, page.alternates]:
                    if (path.parent / links.get(code, "")).resolve() != site / langdir / filename:
                        errors.append(f"{rel}: missing/invalid same-page alternate {code}")
            if not re.search("[\u3400-\u9fff]", "".join(x["label"] for x in page.nav)) and language == "zh-CN":
                errors.append(f"{rel}: Chinese nav lacks Chinese text")
            if re.sub("[^a-z0-9]", "", name.lower()) != "ojnexus":
                for token in SAMPLE_COPY:
                    if token.lower() in html.lower():
                        errors.append(f"{rel}: stale sample {token!r}")
            refs.extend((path, url, tag, key) for tag, key, url in page.refs)
    for role, translations in titles.items():
        if len(translations) < len(LANGUAGES):
            errors.append(f"{role}: translated page titles are identical or missing")
    for css in site.rglob("*.css"):
        for match in re.finditer(r"""url\(\s*(['"]?)([^)'"]+)\1\s*\)""", css.read_text(), re.I):
            refs.append((css, match[2].strip(), "css", "url"))
    ids = {path: page.ids for path, page in parsed.items()}
    local_count = 0
    remote_count = 0
    for src, raw_url, tag, key in refs:
        pathlabel = src.relative_to(site)
        if not raw_url:
            errors.append(f"{pathlabel}: empty {key}")
            continue
        url = urlsplit(raw_url)
        if url.scheme or url.netloc:
            if tag == "a" and url.scheme in {"https", "mailto"}:
                remote_count += 1
            elif tag == "link" and key == "href" and url.scheme == "https":
                remote_count += 1
            elif url.scheme != "data":
                errors.append(f"{pathlabel}: unexpected remote resource/scheme in {tag}.{key}: {raw_url!r}")
            continue
        if url.path.startswith("/"):
            errors.append(f"{pathlabel}: root-relative address breaks Pages subpath {raw_url!r}")
            continue
        local_count += 1
        target = (src.parent / unquote(url.path)).resolve() if url.path else src
        if not target.is_relative_to(site):
            errors.append(f"{pathlabel}: escapes site {raw_url!r}")
            continue
        if target.is_dir():
            target /= "index.html"
        if not target.is_file():
            errors.append(f"{pathlabel}: missing {raw_url!r}")
            continue
        if url.fragment and target.suffix in {".html", ".svg"}:
            if target not in ids:
                if target.suffix == ".svg":
                    ids[target] = {x.get("id") for x in ElementTree.parse(target).iter()}
                else:
                    extra = Page()
                    extra.feed(target.read_text())
                    ids[target] = extra.ids
            if unquote(url.fragment) not in ids[target]:
                errors.append(f"{pathlabel}: missing fragment {raw_url!r}")
    site_bytes = sum(p.stat().st_size for p in site.rglob("*") if p.is_file())
    if site_bytes > budget * 1024:
        errors.append(f"site exceeds {budget} KiB ({site_bytes} bytes)")
    return {"project": name, "ok": not errors, "pages": len(parsed), "site_bytes": site_bytes,
            "render_consistent": check.returncode == 0, "local_references": local_count,
            "external_references_unfetched": remote_count, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="*", type=Path, default=[Path(__file__).resolve().parent.parent])
    parser.add_argument("--site-budget-kib", type=int, default=256)
    args = parser.parse_args()
    success = True
    for project in args.project:
        try:
            result = inspect(project, args.site_budget_kib)
        except (ValueError, KeyError, OSError, ElementTree.ParseError, subprocess.TimeoutExpired) as exc:
            result = {"project": project.name, "ok": False, "errors": [str(exc)]}
        print(json.dumps(result, ensure_ascii=False), flush=True)
        success &= result["ok"]
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
