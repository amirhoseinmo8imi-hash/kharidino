/* =========================================================
   KHARIDINO CATEGORY FEED
   Groups the existing home product cards by category without
   changing Flask routes, models, database or product markup.
   ========================================================= */
(function(){
  'use strict';

  function buildCategoryFeed(){
    const section = document.querySelector('#products');
    if(!section || section.dataset.categoryFeedReady === '1') return;

    const grid = section.querySelector(':scope > .container > .product-grid');
    if(!grid) return;

    const cards = Array.from(grid.querySelectorAll(':scope > .product-card'));
    if(!cards.length) return;

    const groups = new Map();
    cards.forEach(card => {
      const cat = card.querySelector('.product-category');
      const name = cat ? cat.textContent.trim() : 'سایر محصولات';
      const href = cat ? cat.getAttribute('href') : '#products';
      if(!groups.has(name)) groups.set(name,{href,cards:[]});
      groups.get(name).cards.push(card);
    });

    const feed = document.createElement('div');
    feed.className = 'kf-category-feed';
    feed.setAttribute('aria-label','محصولات بر اساس دسته‌بندی');

    let groupIndex = 0;
    groups.forEach((group,name) => {
      const block = document.createElement('section');
      block.className = 'kf-category-block';

      const head = document.createElement('div');
      head.className = 'kf-category-head';
      head.innerHTML =
        '<div class="kf-category-title">' +
          '<span class="kf-icon"><i class="fa-solid fa-layer-group"></i></span>' +
          '<div><h3></h3><small>محصولات پیشنهادی خریدینو</small></div>' +
        '</div>' +
        '<a class="kf-category-more" href="' + (group.href || '#products') + '">مشاهده همه <i class="fa-solid fa-angle-left"></i></a>';
      head.querySelector('h3').textContent = name;

      const rail = document.createElement('div');
      rail.className = 'kf-product-rail';
      rail.setAttribute('role','list');

      group.cards.forEach((card,i) => {
        card.setAttribute('role','listitem');
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

  function init(){
    // Only transform the normal home product area, never search results.
    if(document.body.classList.contains('search-page')) return;
    buildCategoryFeed();
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded',init);
  else init();
})();
