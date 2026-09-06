/* Kharidino animated background + marketplace bootstrap */
(function(){
  'use strict';
  function loadAsset(type, href){
    if(document.querySelector(type + '[data-kharidino-asset="' + href + '"]')) return;
    if(type === 'link'){
      const el=document.createElement('link'); el.rel='stylesheet'; el.href=href; el.dataset.kharidinoAsset=href; document.head.appendChild(el);
    }else{
      const el=document.createElement('script'); el.src=href; el.defer=true; el.dataset.kharidinoAsset=href; document.head.appendChild(el);
    }
  }
  function init(){
    loadAsset('link','/static/css/kharidino-market-fix.css?v=2026-market-fix-2');
    loadAsset('link','/static/css/storefront-home.css?v=2026-storefront-1');
    loadAsset('script','/static/js/mobile-marketplace.js?v=2026-market-2');
    const root=document.querySelector('.site-background');
    if(!root) return;
    const media=root.querySelector('.site-background-media');
    if(media && media.tagName==='VIDEO'){
      media.muted=true; media.loop=true; media.playsInline=true;
      const play=()=>media.play().catch(()=>{}); play();
      document.addEventListener('visibilitychange',()=>{ if(document.hidden) media.pause(); else play(); });
    }
    root.classList.add('background-ready');
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();
