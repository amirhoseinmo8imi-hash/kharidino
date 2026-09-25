/* Kharidino navigation security helpers. */
(function () {
  'use strict';

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? (meta.getAttribute('content') || '') : '';
  }

  document.addEventListener('click', function (event) {
    const link = event.target.closest('a[href]');
    if (!link) return;

    let url;
    try {
      url = new URL(link.href, window.location.origin);
    } catch (_) {
      return;
    }

    if (url.origin !== window.location.origin || url.pathname !== '/logout') {
      return;
    }

    event.preventDefault();

    const token = getCsrfToken();
    if (!token) {
      return;
    }

    const form = document.createElement('form');
    form.method = 'post';
    form.action = url.pathname;
    form.hidden = true;

    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'csrf_token';
    input.value = token;
    form.appendChild(input);

    document.body.appendChild(form);
    form.submit();
  }, true);
})();
