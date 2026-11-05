(function () {
  'use strict';
  const root = document.documentElement;
  const preference = window.matchMedia('(prefers-color-scheme: dark)');
  const key = 'project-pages-theme';
  let saved = null;
  try { saved = localStorage.getItem(key); } catch (_) {}
  let choice = saved === 'dark' || saved === 'light' ? saved : null;
  function apply(theme) {
    root.dataset.theme = theme;
    root.dataset.tone = theme;
    root.style.colorScheme = theme;
    const button = document.querySelector('[data-theme-toggle]');
    if (button) {
      const dark = theme === 'dark';
      const english = root.lang === 'en';
      button.setAttribute('aria-pressed', String(dark));
      const label = english ? (dark ? 'Switch to light theme' : 'Switch to dark theme') : (dark ? '切换到浅色' : '切换到深色');
      button.setAttribute('aria-label', label);
      button.title = label;
    }
  }
  apply(choice || (preference.matches ? 'dark' : 'light'));
  preference.addEventListener('change', function (event) { if (!choice) apply(event.matches ? 'dark' : 'light'); });
  document.addEventListener('DOMContentLoaded', function () {
    apply(root.dataset.theme);
    const button = document.querySelector('[data-theme-toggle]');
    if (button) button.addEventListener('click', function () {
      choice = root.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(key, choice); } catch (_) {}
      apply(choice);
    });
  });
})();
