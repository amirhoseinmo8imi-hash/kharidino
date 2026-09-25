/* Kharidino Ultimate 2026 — storefront/admin enhancement layer */
(function () {
  'use strict';

  const ROOT = '/static/uploads/products/google_candidates/no_image_27/';
  const candidateCache = new Map();

  function slug(value) {
    return String(value || '').normalize('NFKC').trim().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-+|-+$/g, '');
  }

  function productIdFromHref(href) {
    const match = String(href || '').match(/\/product\/(\d+)/);
    return match ? Number(match[1]) : null;
  }

  function candidateUrls(id, name) {
    if (!id || !name) return [];
    const key = `${id}:${name}`;
    if (candidateCache.has(key)) return candidateCache.get(key);
    const folder = `${id}_${slug(name)}`;
    const urls = [];
    for (let n = 1; n <= 15; n++) urls.push(`${ROOT}${encodeURIComponent(folder)}/candidate_${String(n).padStart(2, '0')}.jpg`);
    candidateCache.set(key, urls);
    return urls;
  }

  function probeFirst(urls) {
    return new Promise((resolve) => {
      let cursor = 0;
      const next = () => {
        if (cursor >= urls.length) return resolve('');
        const url = urls[cursor++];
        const img = new Image();
        img.onload = () => resolve(url);
        img.onerror = next;
        img.src = url;
      };
      next();
    });
  }

  function getCardMeta(card, box) {
    const scope = box && box.closest('.ki-slide') ? box.closest('.ki-slide') : (card || box);
    const link = scope?.querySelector('a[href*="/product/"]');
    const href = link ? link.getAttribute('href') : '';
    const id = productIdFromHref(href);
    const title = scope?.querySelector('h1,h2,h3,.item-main strong');
    const name = title ? title.textContent.trim() : (box?.querySelector('img[alt]')?.alt || '');
    return { id, name };
  }

  async function enhanceImageBox(box, id, name) {
    if (!box || !id || !name || box.dataset.kduImageDone === '1') return;
    box.dataset.kduImageDone = '1';
    const current = box.querySelector('img');
    if (current) {
      current.addEventListener('error', async function () {
        if (current.dataset.kdFallbackTried) return;
        current.dataset.kdFallbackTried = '1';
        const fallback = await probeFirst(candidateUrls(id, name));
        if (fallback) current.src = fallback;
      }, { once: true });
      return;
    }
    const icon = box.querySelector('i');
    const fallback = await probeFirst(candidateUrls(id, name));
    if (!fallback) return;
    if (icon) icon.remove();
    const img = document.createElement('img');
    img.src = fallback;
    img.alt = name;
    img.loading = 'lazy';
    img.decoding = 'async';
    img.className = 'kd-ultimate-fallback-image';
    box.appendChild(img);
    box.classList.add('has-kd-image');
  }

  function enhanceStorefrontImages() {
    const selectors = ['.km-product-img', '.ki-slide-product', '.storefront-product-image', '.kc-image'];
    document.querySelectorAll(selectors.join(',')).forEach((box) => {
      const card = box.closest('.km-product,article.storefront-product-card,.kc-card');
      const meta = getCardMeta(card, box);
      if (meta.id && meta.name) enhanceImageBox(box, meta.id, meta.name);
    });
  }

  function enhanceAdminProductImages() {
    document.querySelectorAll('.admin-item').forEach((item) => {
      const strong = item.querySelector('.item-main strong');
      const deleteForm = item.querySelector('form[action*="delete_product"]');
      const box = item.querySelector('.mini-image');
      if (!strong || !deleteForm || !box) return;
      const match = String(deleteForm.getAttribute('action') || '').match(/(\d+)(?:\D*)$/);
      const id = match ? Number(match[1]) : null;
      if (id) enhanceImageBox(box, id, strong.textContent.trim());
    });
  }

  function buildRichProductPanel() {
    const page = document.querySelector('.kd-product-page');
    if (!page || document.querySelector('.kd-ultimate-details')) return;

    const title = page.querySelector('.kd-product-title')?.textContent.trim() || 'محصول';
    const category = page.querySelector('.kd-category-badge')?.textContent.replace(/\s+/g, ' ').trim() || 'بدون دسته';
    const description = page.querySelector('.kd-product-description')?.textContent.trim() || 'توضیحات این محصول هنوز تکمیل نشده است.';
    const price = page.querySelector('.kd-price-main strong')?.textContent.trim() || '0';
    const offers = page.querySelectorAll('.kd-offer-card').length;
    const rating = page.querySelector('.kd-product-stats .kd-stat:nth-child(3) strong')?.textContent.trim() || 'بدون امتیاز';
    const productId = document.querySelector('.kd-gallery')?.dataset.productId || '';
    const offerRows = Array.from(page.querySelectorAll('.kd-offer-card')).slice(0, 8).map((card) => {
      const store = card.querySelector('.kd-store-details strong')?.textContent.trim() || 'فروشگاه';
      const amount = card.querySelector('.kd-offer-price strong')?.textContent.trim() || '—';
      const status = card.classList.contains('available') ? 'موجود' : 'ناموجود';
      return `<div class="kdu-offer-mini"><span>${escapeHtml(store)}</span><strong>${escapeHtml(amount)} تومان</strong><em>${status}</em></div>`;
    }).join('');

    const panel = document.createElement('section');
    panel.className = 'kd-ultimate-details';
    panel.innerHTML = `
      <div class="kdu-tabs" role="tablist">
        <button class="is-active" data-tab="intro">معرفی محصول</button>
        <button data-tab="specs">مشخصات</button>
        <button data-tab="reviews">امتیاز و نظر</button>
        <button data-tab="offers">فروشگاه‌ها</button>
      </div>
      <div class="kdu-pane is-active" data-pane="intro">
        <div class="kdu-intro-grid">
          <div><span class="kdu-kicker">معرفی</span><h2>${escapeHtml(title)}</h2><p>${escapeHtml(description)}</p></div>
          <div class="kdu-summary-card"><strong>انتخاب هوشمند</strong><span>قیمت، موجودی و فروشگاه‌ها را قبل از خرید یکجا بررسی کن.</span><a href="#price-offers">مشاهده پیشنهادها <i class="fa-solid fa-arrow-left"></i></a></div>
        </div>
      </div>
      <div class="kdu-pane" data-pane="specs">
        <div class="kdu-spec-grid">
          ${spec('دسته‌بندی', category)}
          ${spec('شناسه محصول', productId || '—')}
          ${spec('بهترین قیمت', `${price} تومان`)}
          ${spec('فروشگاه‌های فعال', String(offers))}
          ${spec('امتیاز ثبت‌شده', rating)}
          ${spec('وضعیت', offers ? 'پیشنهاد خرید موجود' : 'نیازمند ثبت فروشگاه')}
        </div>
        <div class="kdu-note"><i class="fa-solid fa-circle-info"></i><span>مشخصات فنی دقیق فقط وقتی نمایش داده می‌شود که برای محصول در داده‌های خریدینو ثبت شده باشد؛ از ساختن مشخصات جعلی خودداری شده است.</span></div>
      </div>
      <div class="kdu-pane" data-pane="reviews">
        <div class="kdu-review-head"><div><span class="kdu-kicker">بازخورد مشتری</span><h2>امتیاز محصول</h2></div><div class="kdu-rating-big"><strong>${escapeHtml(rating)}</strong><span>از ۵</span></div></div>
        <div class="kdu-review-empty"><i class="fa-regular fa-star"></i><strong>نظر خودت را ثبت کن</strong><span>امتیاز و متن نظر از همین صفحه ثبت می‌شود و بعد از ارسال در سیستم خریدینو ذخیره خواهد شد.</span></div>
        <form class="kdu-review-form" method="post" action="${escapeHtml(window.location.pathname)}">
          <label>امتیاز <select name="rating"><option value="5">۵ - عالی</option><option value="4">۴ - خوب</option><option value="3">۳ - متوسط</option><option value="2">۲ - ضعیف</option><option value="1">۱ - خیلی ضعیف</option></select></label>
          <label class="kdu-review-text">متن نظر <textarea name="text" rows="4" required placeholder="تجربه‌ات از این محصول را بنویس..."></textarea></label>
          <button type="submit"><i class="fa-solid fa-paper-plane"></i> ثبت نظر</button>
        </form>
      </div>
      <div class="kdu-pane" data-pane="offers">
        <div class="kdu-offer-mini-list">${offerRows || '<div class="kdu-review-empty"><i class="fa-solid fa-store-slash"></i><strong>هنوز پیشنهاد فروشگاهی ثبت نشده</strong></div>'}</div>
      </div>`;

    const benefits = page.querySelector('.kd-benefits');
    if (benefits) benefits.before(panel); else page.querySelector('.container')?.appendChild(panel);

    panel.querySelectorAll('.kdu-tabs button').forEach((button) => {
      button.addEventListener('click', () => {
        panel.querySelectorAll('.kdu-tabs button').forEach((b) => b.classList.toggle('is-active', b === button));
        panel.querySelectorAll('.kdu-pane').forEach((pane) => pane.classList.toggle('is-active', pane.dataset.pane === button.dataset.tab));
      });
    });
  }

  function spec(label, value) {
    return `<div class="kdu-spec"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
  }

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  }

  function postAction(action, productId, nextUrl) {
    const form = document.createElement('form');
    form.method = 'post';
    form.action = action.replace('__PRODUCT_ID__', encodeURIComponent(String(productId)));
    form.style.display = 'none';
    const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    if (token) {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'csrf_token';
      input.value = token;
      form.appendChild(input);
    }
    if (nextUrl) {
      const next = document.createElement('input');
      next.type = 'hidden';
      next.name = 'next';
      next.value = nextUrl;
      form.appendChild(next);
    }
    document.body.appendChild(form);
    form.submit();
  }

  function addQuickActions() {
    const cards = document.querySelectorAll('.km-product, .storefront-product-card, .kc-card');
    cards.forEach((card) => {
      if (card.dataset.kduActions === '1') return;
      const link = card.querySelector('a[href*="/product/"]');
      if (!link) return;
      const id = productIdFromHref(link.getAttribute('href'));
      if (!id) return;
      card.dataset.kduActions = '1';
      const actions = document.createElement('div');
      actions.className = 'kdu-card-actions';
      actions.innerHTML = `<button type="button" class="kdu-card-action" data-kdu-action="favorite" aria-label="افزودن به علاقه‌مندی"><i class="fa-regular fa-heart"></i><span>علاقه‌مندی</span></button><button type="button" class="kdu-card-action" data-kdu-action="compare" aria-label="افزودن به مقایسه"><i class="fa-solid fa-scale-balanced"></i><span>مقایسه</span></button>`;
      actions.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-kdu-action]');
        if (!button) return;
        event.preventDefault();
        event.stopPropagation();
        const action = button.dataset.kduAction;
        if (action === 'favorite') postAction('/favorite/__PRODUCT_ID__', id, window.location.href);
        if (action === 'compare') postAction('/compare/add/__PRODUCT_ID__', id, window.location.href);
      });
      card.appendChild(actions);
    });
  }

  function addProductPageActions() {
    const page = document.querySelector('.kd-product-page');
    if (!page || page.dataset.kduActions === '1') return;
    const gallery = page.querySelector('.kd-gallery');
    const id = gallery?.dataset.productId;
    if (!id) return;
    page.dataset.kduActions = '1';
    const host = page.querySelector('.kd-product-title')?.parentElement || page.querySelector('.kd-product-info') || page;
    const actions = document.createElement('div');
    actions.className = 'kdu-product-actions';
    actions.innerHTML = `<button type="button" class="kdu-primary-action" data-kdu-action="favorite"><i class="fa-regular fa-heart"></i> افزودن به علاقه‌مندی</button><button type="button" class="kdu-secondary-action" data-kdu-action="compare"><i class="fa-solid fa-scale-balanced"></i> مقایسه محصول</button>`;
    actions.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-kdu-action]');
      if (!button) return;
      const action = button.dataset.kduAction;
      if (action === 'favorite') postAction('/favorite/__PRODUCT_ID__', id, window.location.href);
      if (action === 'compare') postAction('/compare/add/__PRODUCT_ID__', id, window.location.href);
    });
    host.appendChild(actions);
  }

  function guardImportantForms() {
    document.querySelectorAll('form').forEach((form) => {
      if (form.dataset.kduGuarded === '1') return;
      const method = (form.getAttribute('method') || 'get').toLowerCase();
      if (method !== 'post') return;
      const action = form.getAttribute('action') || '';
      const important = /checkout|payment\/start|cart_update|cart_remove|order|review/.test(action) || form.classList.contains('kdu-review-form');
      if (!important) return;
      form.dataset.kduGuarded = '1';
      form.addEventListener('submit', () => {
        if (form.dataset.kduSubmitted === '1') return;
        form.dataset.kduSubmitted = '1';
        const button = form.querySelector('button[type="submit"]:not([disabled])');
        if (button) {
          button.disabled = true;
          button.dataset.kduOriginalText = button.textContent.trim();
          button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> در حال پردازش...';
        }
      }, { capture: true });
    });
  }

  function enhanceAdminWorkspace() {
    if (!document.querySelector('.kh-admin-page')) return;
    document.querySelectorAll('.admin-section').forEach((section) => {
      if (section.dataset.kduEnhanced) return;
      const list = section.querySelector('.admin-list');
      const table = section.querySelector('table');
      if (!list && !table) return;
      const toolbar = document.createElement('div');
      toolbar.className = 'kdu-admin-toolbar';
      toolbar.innerHTML = `<div class="kdu-admin-search"><i class="fa-solid fa-magnifying-glass"></i><input type="search" placeholder="جستجوی سریع در این بخش..."><span></span></div>`;
      const anchor = section.querySelector('.admin-title');
      if (anchor) anchor.after(toolbar); else section.prepend(toolbar);
      const input = toolbar.querySelector('input');
      const counter = toolbar.querySelector('span');
      const items = list ? Array.from(list.children).filter((el) => el.classList.contains('admin-item')) : Array.from(table.querySelectorAll('tbody tr'));
      const filter = () => {
        const q = input.value.trim().toLocaleLowerCase('fa-IR');
        let visible = 0;
        items.forEach((item) => {
          const match = !q || item.textContent.toLocaleLowerCase('fa-IR').includes(q);
          item.style.display = match ? '' : 'none';
          if (match) visible++;
        });
        counter.textContent = `${visible} مورد`;
      };
      input.addEventListener('input', filter);
      filter();
      section.dataset.kduEnhanced = '1';
    });
  }

  function init() {
    enhanceStorefrontImages();
    enhanceAdminProductImages();
    buildRichProductPanel();
    addQuickActions();
    addProductPageActions();
    guardImportantForms();
    enhanceAdminWorkspace();
    window.setTimeout(() => {
      enhanceStorefrontImages();
      enhanceAdminProductImages();
      addQuickActions();
      guardImportantForms();
    }, 900);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
