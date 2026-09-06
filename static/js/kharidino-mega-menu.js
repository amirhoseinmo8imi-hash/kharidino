(function(){
  'use strict';

  function escapeText(value){ return value == null ? '' : String(value); }

  function categoryMarkup(categories){
    if(!categories.length) return '<div class="km-category-mega-empty">دسته‌بندی‌ای برای نمایش وجود ندارد.</div>';
    return categories.map(function(cat){
      var href = cat.href || '#categories';
      var name = escapeText(cat.name);
      var icon = escapeText(cat.icon || 'fa-box');
      return '<a class="km-category-mega-link" href="'+href+'">'
        + '<span class="km-category-mega-icon"><i class="fa-solid '+icon+'"></i></span>'
        + '<span>'+name+'</span></a>';
    }).join('');
  }

  function buildMenu(wrapper, categories){
    var panel = wrapper.querySelector('.km-category-mega');
    if(!panel) return;
    panel.innerHTML = categoryMarkup(categories);
    var trigger = wrapper.querySelector('.km-cat-menu-trigger');
    if(trigger){
      trigger.setAttribute('aria-haspopup','true');
      trigger.setAttribute('aria-expanded','false');
      trigger.addEventListener('click',function(event){
        if(window.matchMedia('(max-width: 720px)').matches){
          event.preventDefault();
          var open = wrapper.classList.toggle('is-open');
          trigger.setAttribute('aria-expanded',open?'true':'false');
        }
      });
    }
    wrapper.addEventListener('mouseenter',function(){ if(trigger) trigger.setAttribute('aria-expanded','true'); });
    wrapper.addEventListener('mouseleave',function(){ if(trigger) trigger.setAttribute('aria-expanded','false'); });
    wrapper.addEventListener('focusout',function(){
      setTimeout(function(){ if(!wrapper.contains(document.activeElement) && trigger) trigger.setAttribute('aria-expanded','false'); },0);
    });
  }

  function getHomeCategories(){
    var local = Array.prototype.slice.call(document.querySelectorAll('.km-home .km-categories .km-cat'));
    if(local.length){
      return Promise.resolve(local.map(function(el){
        var a=el.closest('a') || el;
        var icon=el.querySelector('.km-cat-icon i');
        return {href:a.getAttribute('href'),name:(el.querySelector('strong')||{}).textContent||'',icon:icon ? icon.className.replace('fa-solid ','') : 'fa-box'};
      }));
    }
    return fetch('/',{credentials:'same-origin',headers:{'X-Kharidino-Category-Menu':'1'}})
      .then(function(r){return r.ok?r.text():'';})
      .then(function(html){
        var doc=new DOMParser().parseFromString(html,'text/html');
        return Array.prototype.slice.call(doc.querySelectorAll('.km-categories .km-cat')).map(function(el){
          var a=el.closest('a') || el;
          var icon=el.querySelector('.km-cat-icon i');
          return {href:a.getAttribute('href'),name:(el.querySelector('strong')||{}).textContent||'',icon:icon ? icon.className.replace('fa-solid ','') : 'fa-box'};
        });
      }).catch(function(){return [];});
  }

  function init(){
    var links=Array.prototype.slice.call(document.querySelectorAll('.km-nav-inner a'));
    links.forEach(function(link){
      if(!/دسته‌بندی|دسته بندی/.test(link.textContent||'')) return;
      if(link.parentElement && link.parentElement.classList.contains('km-cat-menu-wrap')) return;
      var wrapper=document.createElement('div');
      wrapper.className='km-cat-menu-wrap';
      var trigger=link.cloneNode(true);
      trigger.className='km-cat-menu-trigger';
      trigger.innerHTML='<i class="fa-solid fa-bars"></i><span>دسته‌بندی کالاها</span><i class="fa-solid fa-chevron-down km-cat-chevron"></i>';
      trigger.removeAttribute('href');
      trigger.setAttribute('tabindex','0');
      var panel=document.createElement('div');
      panel.className='km-category-mega';
      panel.setAttribute('role','menu');
      panel.innerHTML='<div class="km-category-mega-empty">در حال بارگذاری دسته‌بندی‌ها…</div>';
      wrapper.appendChild(trigger); wrapper.appendChild(panel);
      link.replaceWith(wrapper);
      getHomeCategories().then(function(categories){buildMenu(wrapper,categories);});
      document.addEventListener('click',function(event){
        if(!wrapper.contains(event.target)){wrapper.classList.remove('is-open');trigger.setAttribute('aria-expanded','false');}
      });
    });
    document.querySelectorAll('.km-topbar').forEach(function(topbar){
      topbar.addEventListener('scroll',function(){document.querySelectorAll('.km-cat-menu-wrap.is-open').forEach(function(w){w.classList.remove('is-open');});},{passive:true});
    });
    function setMegaTop(){
      document.querySelectorAll('.km-cat-menu-wrap').forEach(function(w){
        var r=w.getBoundingClientRect();
        w.style.setProperty('--km-mega-top',Math.max(10,r.bottom+2)+'px');
      });
    }
    window.addEventListener('resize',setMegaTop,{passive:true});
    setMegaTop();
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();
