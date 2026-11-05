/* Copy only the selected code block; README content is never evaluated. */
(() => {
  'use strict';
  const timers = new WeakMap();
  const legacyCopy = text => {
    const field = document.createElement('textarea');
    field.value = text;
    field.setAttribute('readonly', '');
    field.style.cssText = 'position:fixed;left:-10000px;top:0;opacity:0';
    document.body.append(field);
    field.select();
    try { if (!document.execCommand('copy')) throw new Error('Copy unavailable'); }
    finally { field.remove(); }
  };
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-copy-code]');
    if (!button) return;
    const block = button.closest('[data-code-block]');
    const code = block?.querySelector('pre code');
    if (!code) return;
    const status = block.querySelector('.docs-copy-status');
    const previousFocus = document.activeElement;
    try {
      if (navigator.clipboard?.writeText && window.isSecureContext) {
        await navigator.clipboard.writeText(code.textContent);
      } else { legacyCopy(code.textContent); }
      button.textContent = '已复制';
      button.dataset.copyState = 'success';
      if (status) status.textContent = '代码已复制';
    } catch {
      button.textContent = '请选中复制';
      button.dataset.copyState = 'failed';
      if (status) status.textContent = '复制不可用，请选中代码手动复制';
    } finally { previousFocus?.focus({ preventScroll: true }); }
    clearTimeout(timers.get(button));
    timers.set(button, setTimeout(() => {
      button.textContent = '复制';
      delete button.dataset.copyState;
      if (status) status.textContent = '';
    }, 2200));
  });
  const imageFallback = image => {
    if (image.dataset.fallbackShown) return;
    image.dataset.fallbackShown = 'true';
    const outer = image.closest('a');
    const fallback = document.createElement(outer ? 'span' : 'a');
    fallback.className = 'docs-image-fallback';
    if (!outer) fallback.href = image.dataset.original;
    fallback.textContent = (image.alt || '图片') + (outer ? ' · 图片加载失败' : ' · 查看原图');
    if (outer) {
      const original = document.createElement('a');
      original.className = 'docs-image-original';
      original.href = image.dataset.original;
      original.textContent = '查看原图';
      outer.after(original);
    }
    image.replaceWith(fallback);
  };
  document.querySelectorAll('img.docs-image[data-original]').forEach(image => {
    image.addEventListener('error', () => imageFallback(image), { once: true });
    if (image.complete && !image.naturalWidth) imageFallback(image);
  });
  const links = [...document.querySelectorAll('.docs-toc a[href^="#"]')];
  const byId = new Map(links.map(link => [decodeURIComponent(link.hash.slice(1)), link]));
  const headings = [...document.querySelectorAll('.docs-markdown :is(h1,h2,h3)[id]')];
  const active = id => {
    links.forEach(link => link.removeAttribute('aria-current'));
    byId.get(id)?.setAttribute('aria-current', 'location');
  };
  if ('IntersectionObserver' in window && headings.length) {
    const visible = new Set();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => entry.isIntersecting ? visible.add(entry.target) : visible.delete(entry.target));
      const first = [...visible].sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0];
      if (first) active(first.id);
    }, { rootMargin: '-100px 0px -65% 0px', threshold: 0 });
    headings.forEach(heading => observer.observe(heading));
  }
  links.forEach(link => link.addEventListener('click', () => {
    active(decodeURIComponent(link.hash.slice(1)));
    if (matchMedia('(max-width:767px)').matches) link.closest('details')?.removeAttribute('open');
  }));
})();
