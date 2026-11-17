"""Check the bilingual project homepage in Chrome through the W3C WebDriver API.

Requires Chrome/Chromium and chromedriver on PATH. Uses only the Python stdlib.
"""
import argparse
import base64
import contextlib
import functools
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

HTTP = build_opener(ProxyHandler({}))
PAGES = ("index.html", "features.html", "download.html", "community.html")
ELEMENT = "element-6066-11e4-a52e-4f735466cecf"


def call(method, url, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=data, method=method,
                      headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with HTTP.open(request, timeout=20) as response:
            return json.load(response)["value"]
    except HTTPError as exc:
        try:
            reason = json.loads(exc.read())["value"]["message"]
        except (ValueError, KeyError, TypeError):
            reason = str(exc.reason)
        raise RuntimeError(f"{method} {url}: {reason}") from exc


class QuietServer(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def translate_path(self, path):
        # Expose this site's files only, beneath /project/ like a GitHub Pages site.
        if not path.startswith("/project/"):
            return str(Path(self.directory) / "absent-http-route")
        return super().translate_path(path[len("/project"):])


@contextlib.contextmanager
def serve(site):
    handler = functools.partial(QuietServer, directory=site)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .03},
                              daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/project/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@contextlib.contextmanager
def webdriver(path):
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryFile(mode="w+b") as log:
        proc = subprocess.Popen([path, f"--port={port}"], stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline and proc.poll() is None:
                try:
                    if call("GET", url + "/status")["ready"]:
                        break
                except (URLError, OSError, RuntimeError):
                    pass
                time.sleep(.1)
            else:
                log.seek(0)
                raise RuntimeError("chromedriver did not start: " + log.read(1024).decode(errors="replace"))
            yield url
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


class Chrome:
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def cmd(self, method, suffix, payload=None):
        return call(method, self.endpoint + suffix, payload)

    def js(self, script, *args):
        return self.cmd("POST", "/execute/sync", {"script": script, "args": args})

    def find(self, selector):
        return self.cmd("POST", "/element", {"using": "css selector", "value": selector})[ELEMENT]

    def click(self, selector):
        self.cmd("POST", "/element/" + self.find(selector) + "/click", {})

    def key(self, key):
        self.cmd("POST", "/actions", {"actions": [{"type": "key", "id": "keyboard", "actions": [
            {"type": "keyDown", "value": key}, {"type": "keyUp", "value": key}]}]})

    def goto(self, url):
        self.cmd("POST", "/url", {"url": url})

    def wait(self, predicate, message):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.05)
        raise ValueError(message)

    def expect_url(self, url):
        self.wait(lambda: self.cmd("GET", "/url") == url, f"expected navigation to {url}")

    def capture(self, directory, name):
        if directory:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (name + ".png")).write_bytes(base64.b64decode(self.cmd("GET", "/screenshot")))


@contextlib.contextmanager
def session(driver, binary, width, height, js=True):
    # User-data, preferences and all browser state belong only to this session.
    with tempfile.TemporaryDirectory(prefix="project-website-chrome-") as profile:
        opts = {"args": ["--headless=new", "--disable-dev-shm-usage", "--disable-background-networking",
                         "--no-first-run", f"--user-data-dir={profile}"]}
        if getattr(os, "geteuid", lambda: None)() == 0:
            opts["args"].append("--no-sandbox")
        if binary:
            opts["binary"] = binary
        if not js:
            opts["prefs"] = {"profile.managed_default_content_settings.javascript": 2}
        caps = {"browserName": "chrome", "goog:chromeOptions": opts,
                "goog:loggingPrefs": {"browser": "ALL"}}
        sid = call("POST", driver + "/session", {"capabilities": {"alwaysMatch": caps}})["sessionId"]
        chrome = Chrome(driver + "/session/" + sid)
        try:
            chrome.cmd("POST", "/window/rect", {"width": width, "height": height})
            if width < 500:
                # Headless Chrome imposes a minimum desktop window width.
                chrome.cmd("POST", "/goog/cdp/execute", {"cmd": "Emulation.setDeviceMetricsOverride",
                    "params": {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": True}})
            yield chrome
        finally:
            chrome.cmd("DELETE", "")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check_pages(browser, base, width):
    for locale in ("", "en/"):
        for filename in PAGES:
            browser.goto(base + locale + filename)
            state = browser.js("""
              const h = document.querySelector('main h1');
              return {heading:h && h.innerText.trim(), width:innerWidth,
                      scroll:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth),
                      lang:document.documentElement.lang,
                      missing:[...document.images].filter(i => i.loading !== "lazy" && i.getClientRects().length && (!i.complete || !i.naturalWidth)).length};
            """)
            require(state["heading"] and state["lang"] == ("en" if locale else "zh-CN"),
                    f"{locale}{filename}: missing translated content")
            require(state["width"] == width and state["scroll"] <= width + 1,
                    f"{locale}{filename}: viewport/overflow {state}")
            require(not state["missing"], f"{locale}{filename}: unloaded image")


def language(browser, code):
    browser.click(".language-picker summary")
    browser.click(f'.language-picker a[hreflang="{code}"]')


def log_check(browser):
    errors = [m["message"] for m in browser.cmd("POST", "/se/log", {"type": "browser"})
              if m["level"] in {"WARNING", "SEVERE"}]
    require(not errors, "browser warnings/errors: " + " | ".join(errors)[:1200])


def execute(site, driver_path, binary, shots, passed):
    with serve(site) as base, webdriver(driver_path) as driver:
        with session(driver, binary, 1280, 850) as browser:
            check_pages(browser, base, 1280)
            passed.append("desktop-8-pages")
            browser.goto(base + "index.html")
            browser.capture(shots, "desktop-zh")
            browser.key("\ue004")  # Tab
            require(browser.js("return document.activeElement.matches('.skip-link')"), "skip link focus")
            browser.key("\ue007")  # Enter
            browser.expect_url(base + "index.html#main")
            browser.click('.main-nav a[href$="features.html"]')
            browser.click(".theme-picker summary")
            browser.click('[data-theme-choice="dark"]')
            language(browser, "en")
            browser.expect_url(base + "en/features.html")
            browser.cmd("POST", "/refresh", {})
            require(browser.js("return document.documentElement.dataset.colorMode") == "dark",
                    "dark theme did not persist across language and reload")
            browser.capture(shots, "desktop-en-dark")
            for choice in ("system", "light"):
                browser.click(".theme-picker summary")
                browser.click(f'[data-theme-choice="{choice}"]')
                require(browser.js("return document.documentElement.dataset.theme") == choice,
                        f"theme choice {choice}")
            log_check(browser)
            passed.append("desktop-keyboard-locale-themes-console")
        with session(driver, binary, 320, 750) as browser:
            check_pages(browser, base, 320)
            passed.append("mobile-8-pages")
            browser.goto(base + "index.html")
            browser.capture(shots, "mobile-zh")
            browser.click(".menu-toggle")
            require(browser.js("return document.querySelector('.menu-toggle').getAttribute('aria-expanded')") == "true",
                    "mobile menu failed to open")
            browser.key("\ue00c")  # Escape
            require(browser.js("return document.activeElement.matches('.menu-toggle') && document.activeElement.getAttribute('aria-expanded') === 'false'"),
                    "Escape failed to close menu or restore focus")
            browser.click(".menu-toggle")
            browser.click('.main-nav a[href$="download.html"]')
            language(browser, "en")
            browser.expect_url(base + "en/download.html")
            browser.capture(shots, "mobile-en")
            log_check(browser)
            passed.append("mobile-menu-keyboard-locale-console")
        with session(driver, binary, 390, 780, js=False) as browser:
            browser.goto(base + "index.html")
            require(not browser.js("return document.documentElement.classList.contains('js')"),
                    "scripts unexpectedly active in the no-JS session")
            browser.click('.main-nav a[href$="community.html"]')
            language(browser, "en")
            browser.expect_url(base + "en/community.html")
            require(browser.js("return document.querySelector('main h1').innerText.trim()"), "no-JS empty page")
            log_check(browser)
            passed.append("no-js-menu-language-and-reading")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--chromedriver", default=shutil.which("chromedriver"))
    parser.add_argument("--chrome", default=shutil.which("google-chrome") or shutil.which("chromium"))
    args = parser.parse_args()
    passed = []
    errors = []
    try:
        require(args.chromedriver, "chromedriver not found on PATH")
        site = (args.project / "site").resolve()
        require((site / "index.html").is_file(), "missing site/index.html")
        execute(site, args.chromedriver, args.chrome, args.screenshots, passed)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        errors.append(str(exc))
    print(json.dumps({"project": args.project.name, "ok": not errors, "checks": passed,
                      "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
