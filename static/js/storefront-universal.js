/* KHARIDINO UNIVERSAL JS
   Shared fixes that must work across every storefront page.
*/
(function(){
  'use strict';

  function init(){
    // Fix both legacy and newer mobile-menu naming conventions.
    const button = document.querySelector('.mobile-menu-toggle, .mobile-menu-btn, #mobileMenuBtn');
    const menu = document.querySelector('.main-nav, .nav-links');
    if(button && menu && !button.dataset.kfMenuBound){
      button.dataset.kfMenuBound='1';
      button.addEventListener('click', function(){
        const open=menu.classList.toggle('mobile-open');
        button.classList.toggle('active', open);
        button.setAttribute('aria-expanded', open ? 'true' : 'false');
        const icon=button.querySelector('i');
        if(icon){ icon.classList.toggle('fa-bars', !open); icon.classList.toggle('fa-xmark', open); }
      });
    }

    // Broken remote/product images should never leave a collapsed card.
    document.querySelectorAll('img').forEach(function(img){
      if(img.dataset.kfFallback) return;
      img.dataset.kfFallback='1';
      img.addEventListener('error', function(){
        img.classList.add('kf-image-error');
        img.style.visibility='hidden';
        const box=img.parentElement;
        if(box && !box.querySelector('.kf-image-fallback')){
          const fallback=document.createElement('span');
          fallback.className='kf-image-fallback';
          fallback.innerHTML='<i class="fa-solid fa-image"></i><small>تصویر در دسترس نیست</small>';
          box.appendChild(fallback);
        }
      }, {once:true});
    });

    // Native lazy loading for older templates that forgot the attribute.
    document.querySelectorAll('img').forEach(function(img){
      if(!img.loading) img.loading='lazy';
    });

    // Register the existing PWA service worker when supported.
    if('serviceWorker' in navigator && location.protocol !== 'file:'){
      navigator.serviceWorker.register('/static/sw.js').catch(function(){});
    }
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
