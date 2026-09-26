/* Kharidino 2026 — final site-wide interaction layer */
(function(){
  'use strict';

  function ready(fn){
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',fn,{once:true});
    else fn();
  }

  ready(function(){
    const body=document.body;
    let backTop=null;

    function onScroll(){
      body.classList.toggle('kh-header-scrolled',window.scrollY>12);
      if(backTop) backTop.classList.toggle('is-visible',window.scrollY>520);
    }
    window.addEventListener('scroll',onScroll,{passive:true});
    onScroll();

    /* Back-to-top */
    backTop=document.createElement('button');
    backTop.type='button';
    backTop.className='kh-back-top';
    backTop.setAttribute('aria-label','بازگشت به بالای صفحه');
    backTop.innerHTML='<i class="fa-solid fa-arrow-up"></i>';
    document.body.appendChild(backTop);
    backTop.addEventListener('click',function(){
      window.scrollTo({top:0,behavior:'smooth'});
    });
    onScroll();

    /* Keyboard shortcut: / focuses the main search. */
    document.addEventListener('keydown',function(e){
      if(e.key!=='/' || e.ctrlKey || e.metaKey || e.altKey) return;
      const t=e.target;
      if(t && ['INPUT','TEXTAREA','SELECT'].includes(t.tagName)) return;
      const input=document.querySelector('.km-search input[name="q"]');
      if(!input)return;
      e.preventDefault();
      input.focus();
      input.select();
    });

    /* Safe image fallback: never leave a broken-image icon in product cards. */
    document.querySelectorAll('img').forEach(function(img){
      img.addEventListener('error',function(){
        if(img.dataset.khFallback==='1')return;
        img.dataset.khFallback='1';
        img.removeAttribute('srcset');
        img.src='data:image/svg+xml;charset=UTF-8,'+encodeURIComponent(
          '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480">'+
          '<rect width="640" height="480" fill="#f7f8fa"/>'+
          '<circle cx="320" cy="220" r="72" fill="#eceff2"/>'+
          '<path d="M275 245l28-32 24 25 20-23 43 48H250z" fill="#c8cdd3"/>'+
          '<text x="320" y="350" text-anchor="middle" font-family="Arial" font-size="22" fill="#8b929b">خریدینو</text>'+
          '</svg>'
        );
      },{once:true});
    });

    /* Mark external offer links without changing their destination. */
    document.querySelectorAll('a[href]').forEach(function(a){
      try{
        const u=new URL(a.href,location.href);
        if(u.origin!==location.origin && u.protocol.startsWith('http')){
          a.setAttribute('rel',a.getAttribute('rel')||'noopener noreferrer');
        }
      }catch(_){}
    });

    /* Preserve the current search when users move through catalog actions. */
    const searchInput=document.querySelector('.km-search input[name="q"]');
    if(searchInput && searchInput.value.trim()){
      document.querySelectorAll('a[href*="/compare"],a[href*="/stores"]').forEach(function(a){
        a.dataset.khSearchContext=searchInput.value.trim();
      });
    }

    /* Small touch feedback without interfering with links/forms. */
    document.addEventListener('pointerdown',function(e){
      const el=e.target.closest('a,button');
      if(el) el.classList.add('kh-pressed');
    },{passive:true});
    document.addEventListener('pointerup',function(){
      document.querySelectorAll('.kh-pressed').forEach(function(el){el.classList.remove('kh-pressed');});
    },{passive:true});
  });
})();