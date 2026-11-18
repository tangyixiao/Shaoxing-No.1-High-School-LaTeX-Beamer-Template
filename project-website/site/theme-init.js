"use strict";

// Keep the preference shared by every page and locale beneath this site's root.
// This runs synchronously in the head so a saved theme is applied before paint.
(() => {
  const root = document.documentElement;
  const choices = ["light", "dark", "system"];
  const valid = (value) => choices.includes(value);
  const fallback = valid(root.dataset.defaultTheme) ? root.dataset.defaultTheme : "light";
  const siteRoot = new URL(root.dataset.siteRoot || "./", window.location.href);
  const storageKey = "project-theme:" + siteRoot.pathname;
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  let choice = fallback;

  try {
    const saved = window.localStorage.getItem(storageKey);
    if (valid(saved)) choice = saved;
  } catch (_) {
    // Theme selection still works for this page when storage is unavailable.
  }

  const apply = () => {
    const mode = choice === "system" ? (media.matches ? "dark" : "light") : choice;
    root.dataset.theme = choice;
    root.dataset.colorMode = mode;
    document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
      meta.content = mode === "dark" ? "#18191b" : "#ffffff";
      meta.removeAttribute("media");
    });
    document.dispatchEvent(new CustomEvent("project-theme-change"));
  };

  window.ProjectTheme = {
    getChoice: () => choice,
    setChoice: (value) => {
      if (!valid(value)) return;
      choice = value;
      try { window.localStorage.setItem(storageKey, value); } catch (_) { /* Optional storage. */ }
      apply();
    }
  };

  const onSystemChange = () => { if (choice === "system") apply(); };
  if (media.addEventListener) media.addEventListener("change", onSystemChange);
  else if (media.addListener) media.addListener(onSystemChange);

  window.addEventListener("storage", (event) => {
    if (event.key !== storageKey && event.key !== null) return;
    choice = valid(event.newValue) ? event.newValue : fallback;
    apply();
  });
  apply();
})();
