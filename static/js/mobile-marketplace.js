/* Kharidino marketplace UX */
(function () {
  'use strict';
  const mobile = () => window.matchMedia('(max-width: 768px)').matches;

  function buildCategoryFeed() {
    const section = document.querySelector('#products');
    if (!section || section.dataset.categoryFeedReady === '1') return;
    const grid = section.querySelector(':scope > .container > .product-grid');
    if (!grid) return;
    const cards = Array.from(grid.querySelectorAll(':scope > .product-card'));
    if (!cards.length) return;

    const groups = new Map();
    cards.forEach(card => {
      const cat = card.querySelector('.product-category');
      const name = cat ? cat.textContent.trim() : 'سایر محصولات';
      const href = cat ? (cat.getAttribute('href') || '#products') : '#products';
      if (!groups.has(name)) groups.set(name, { href, cards: [] });
      groups.get(name).cards.push(card);
    });

    const feed = document.createElement('div');
    feed.className = 'kf-category-feed';
    feed.setAttribute('aria-label', 'محصولات بر اساس دسته‌بندی');

    let groupIndex = 0;
    groups.forEach((group, name) => {
      const block = document.createElement('section');
      block.className = 'kf-category-block';

      const head = document.createElement('div');
      head.className = 'kf-category-head';
      head.innerHTML = '<div class="kf-category-title"><span class="kf-icon"><i class="fa-solid fa-layer-group"></i></span><div><h3></h3><small>محصولات پیشنهادی خریدینو</small></div></div><a class="kf-category-more"></a>';
      head.querySelector('h3').textContent = name;
      const more = head.querySelector('.kf-category-more');
      more.href = group.href;
      more.innerHTML = 'مشاهده همه <i class="fa-solid fa-angle-left"></i>';

      const rail = document.createElement('div');
      rail.className = 'kf-product-rail';
      rail.setAttribute('role', 'list');

      group.cards.forEach((card, i) => {
        card.setAttribute('role', 'listitem');
        card.style.animationDelay = ((i + groupIndex) * 35) + 'ms';
        rail.appendChild(card);
      });

      block.appendChild(head);
      block.appendChild(rail);
      feed.appendChild(block);
      groupIndex++;
    });

    grid.replaceWith(feed);
    section.dataset.categoryFeedReady = '1';
  }

  function enhanceHome() {
    if (!document.querySelector('#products')) return;
    buildCategoryFeed();
    if (!mobile()) return;

    document.querySelectorAll('.product-grid').forEach((grid, index) => {
      if (grid.dataset.mobileEnhanced) return;
      grid.dataset.mobileEnhanced = '1';
      if (index === 0) grid.classList.add('mobile-market-feed');
    });

    const categoryGrid = document.querySelector('.category-grid');
    if (categoryGrid) categoryGrid.classList.add('mobile-category-rail');

    const section = document.querySelector('.search-result-section') || document.querySelector('#products');
    if (section && !section.querySelector('.mobile-quick-filters')) {
      const bar = document.createElement('div');
      bar.className = 'mobile-quick-filters';
      bar.innerHTML = '<button type="button" data-sort="price_low"><i class="fa-solid fa-arrow-down-wide-short"></i> ارزان‌ترین</button>' +
        '<button type="button" data-sort="newest"><i class="fa-solid fa-clock"></i> جدیدترین</button>' +
        '<button type="button" data-sort="price_high"><i class="fa-solid fa-arrow-up-wide-short"></i> گران‌ترین</button>' +
        '<button type="button" class="filter-open"><i class="fa-solid fa-sliders"></i> فیلتر</button>';
      const header = section.querySelector('.section-header');
      if (header) header.after(bar);

      bar.querySelectorAll('[data-sort]').forEach(btn => {
        btn.addEventListener('click', () => {
          const select = document.querySelector('.discovery-filters select[name="sort"]');
          if (!select) return;
          select.value = btn.dataset.sort;
          const form = select.closest('form');
          if (form) form.submit();
        });
      });

      const filter = bar.querySelector('.filter-open');
      if (filter) filter.addEventListener('click', openFilterSheet);
    }
  }

  function openFilterSheet() {
    const existing = document.querySelector('.mobile-filter-sheet');
    if (existing) { existing.classList.add('is-open'); return; }
    const source = document.querySelector('.discovery-filters');
    if (!source) return;
    const sheet = document.createElement('div');
    sheet.className = 'mobile-filter-sheet';
    sheet.innerHTML = '<div class="mobile-sheet-backdrop"></div><div class="mobile-sheet-panel" role="dialog" aria-modal="true"><div class="mobile-sheet-head"><strong>فیلتر و مرتب‌سازی</strong><button type="button" class="sheet-close"><i class="fa-solid fa-xmark"></i></button></div><div class="mobile-sheet-body"></div><div class="mobile-sheet-actions"><button type="button" class="sheet-reset">پاک کردن</button><button type="button" class="sheet-apply">اعمال فیلتر</button></div></div>';
    document.body.appendChild(sheet);
    const body = sheet.querySelector('.mobile-sheet-body');
    ['input[name="q"]','select[name="category"]','select[name="sort"]'].forEach(sel => {
      const el = source.querySelector(sel);
      if (el) { const clone = el.cloneNode(true); clone.classList.add('sheet-control'); body.appendChild(clone); }
    });
    requestAnimationFrame(() => sheet.classList.add('is-open'));
    const close = () => sheet.classList.remove('is-open');
    sheet.querySelector('.sheet-close').onclick = close;
    sheet.querySelector('.mobile-sheet-backdrop').onclick = close;
    sheet.querySelector('.sheet-reset').onclick = () => {
      body.querySelectorAll('input').forEach(x => x.value = '');
      body.querySelectorAll('select').forEach(x => x.selectedIndex = 0);
    };
    sheet.querySelector('.sheet-apply').onclick = () => {
      body.querySelectorAll('.sheet-control').forEach(control => {
        const original = source.querySelector(`[name="${control.name}"]`);
        if (original) original.value = control.value;
      });
      source.closest('form').submit();
    };
  }

  document.addEventListener('DOMContentLoaded', enhanceHome);
  window.addEventListener('resize', () => { if (mobile()) enhanceHome(); });
})();
