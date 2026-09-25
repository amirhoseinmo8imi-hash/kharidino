(function(){
  'use strict';

  function escapeText(value){ return value == null ? '' : String(value); }

  function categoryMarkup(categories){
    if(!categories.length) return '<div class="km-category-mega-empty">دسته‌بندی‌ای برای نمایش وجود ندارد.</div>';
    return categories.map(function(cat){
      var href = cat.href || '#categories';
      var name = escapeText(cat.name);
      var icon = escapeText(cat.icon || 'fa-box');
      return '<a class="km-category-mega-link" role="menuitem" href="'+href+'">'
        + '<span class="km-category-mega-icon"><i class="fa-solid '+icon+'"></i></span>'
        + '<span>'+name+'</span></a>';
    }).join('');
  }

  function positionMenu(wrapper){
    var trigger=wrapper.querySelector('.km-cat-menu-trigger');
    if(!trigger) return;
    var r=trigger.getBoundingClientRect();
    var panelWidth=Math.min(900,window.innerWidth-32);
    var right=Math.max(16,window.innerWidth-r.right);
    if(window.innerWidth<=430) right=10;
    if(window.innerWidth<=720) panelWidth=window.innerWidth-(right*2);
    wrapper.style.setProperty('--km-mega-top',Math.max(8,r.bottom+2)+'px');
    wrapper.style.setProperty('--km-mega-right',right+'px');
    wrapper.style.setProperty('--km-mega-width',Math.max(0,panelWidth)+'px');
  }

  function buildMenu(wrapper, categories){
    var panel = wrapper.querySelector('.km-category-mega');
    if(!panel) return;
    panel.innerHTML = categoryMarkup(categories);
    var trigger = wrapper.querySelector('.km-cat-menu-trigger');
    if(trigger){
      trigger.setAttribute('aria-haspopup','true');
      trigger.setAttribute('aria-expanded','false');
      trigger.setAttribute('role','button');
      trigger.addEventListener('click',function(event){
        if(window.matchMedia('(max-width: 720px)').matches){
          event.preventDefault();
          positionMenu(wrapper);
          var open = wrapper.classList.toggle('is-open');
          trigger.setAttribute('aria-expanded',open?'true':'false');
        }
      });
      trigger.addEventListener('keydown',function(event){
        if(event.key==='Enter' || event.key===' '){
          event.preventDefault();
          positionMenu(wrapper);
          var open=wrapper.classList.toggle('is-open');
          trigger.setAttribute('aria-expanded',open?'true':'false');
        }
        if(event.key==='Escape'){
          wrapper.classList.remove('is-open');
          trigger.setAttribute('aria-expanded','false');
          trigger.blur();
        }
      });
    }
    wrapper.addEventListener('mouseenter',function(){ positionMenu(wrapper); if(trigger) trigger.setAttribute('aria-expanded','true'); });
    wrapper.addEventListener('mouseleave',function(){ if(trigger) trigger.setAttribute('aria-expanded','false'); });
    wrapper.addEventListener('focusout',function(){
      setTimeout(function(){ if(!wrapper.contains(document.activeElement) && trigger) trigger.setAttribute('aria-expanded','false'); },0);
    });
  }

  function readCategoriesFromDocument(doc){
    return Array.prototype.slice.call(doc.querySelectorAll('.km-categories .km-cat')).map(function(el){
      var a=el.closest('a') || el;
      var icon=el.querySelector('.km-cat-icon i');
      return {href:a.getAttribute('href'),name:(el.querySelector('strong')||{}).textContent||'',icon:icon ? icon.className.replace(/^fa-solid\s+/,'') : 'fa-box'};
    });
  }

  function getHomeCategories(){
    var local = readCategoriesFromDocument(document);
    if(local.length) return Promise.resolve(local);
    return fetch('/',{credentials:'same-origin',headers:{'X-Kharidino-Category-Menu':'1'}})
      .then(function(r){return r.ok?r.text():'';})
      .then(function(html){
        if(!html) return [];
        return readCategoriesFromDocument(new DOMParser().parseFromString(html,'text/html'));
      }).catch(function(){return [];});
  }

  function init(){
    var wrappers=Array.prototype.slice.call(document.querySelectorAll('.km-cat-menu-wrap'));

    wrappers.forEach(function(wrapper){
      var trigger=wrapper.querySelector('.km-cat-menu-trigger');
      var panel=wrapper.querySelector('.km-category-mega');
      if(!trigger || !panel || wrapper.dataset.kmMegaReady==='1') return;
      wrapper.dataset.kmMegaReady='1';

      function positionMenu(){
        var r=trigger.getBoundingClientRect();
        var top=Math.min(window.innerHeight-80,Math.max(70,r.bottom+2));
        wrapper.style.setProperty('--km-mega-top',top+'px');
      }

      function setOpen(open){
        positionMenu();
        wrapper.classList.toggle('is-open',!!open);
        trigger.setAttribute('aria-expanded',open?'true':'false');
      }

      function activate(id){
        wrapper.querySelectorAll('.km-mega-side-item').forEach(function(item){
          item.classList.toggle('is-active',item.getAttribute('data-mega-target')===id);
        });
        wrapper.querySelectorAll('.km-mega-panel').forEach(function(item){
          item.classList.toggle('is-active',item.id===id);
        });
      }

      var sideItems=Array.prototype.slice.call(wrapper.querySelectorAll('.km-mega-side-item'));
      sideItems.forEach(function(item,index){
        item.addEventListener('mouseenter',function(){
          activate(item.getAttribute('data-mega-target'));
          setOpen(true);
        });
        item.addEventListener('focus',function(){
          activate(item.getAttribute('data-mega-target'));
          setOpen(true);
        });
        item.addEventListener('click',function(event){
          if(window.matchMedia('(max-width: 720px)').matches){
            event.preventDefault();
            activate(item.getAttribute('data-mega-target'));
          }
        });
        if(index===0) activate(item.getAttribute('data-mega-target'));
      });

      wrapper.addEventListener('mouseenter',function(){ setOpen(true); });
      wrapper.addEventListener('mouseleave',function(){
        if(window.innerWidth>720) setOpen(false);
      });

      trigger.addEventListener('click',function(event){
        event.preventDefault();
        setOpen(!wrapper.classList.contains('is-open'));
      });

      trigger.addEventListener('keydown',function(event){
        if(event.key==='Enter' || event.key===' '){
          event.preventDefault();
          setOpen(!wrapper.classList.contains('is-open'));
        } else if(event.key==='Escape'){
          setOpen(false);
          trigger.blur();
        }
      });

      panel.addEventListener('mouseenter',function(){ setOpen(true); });
      panel.addEventListener('mouseleave',function(){
        if(window.innerWidth>720) setOpen(false);
      });

      window.addEventListener('resize',function(){
        if(wrapper.classList.contains('is-open')) positionMenu();
      },{passive:true});
      window.addEventListener('scroll',function(){
        if(wrapper.classList.contains('is-open')) positionMenu();
      },{passive:true});
    });

    document.addEventListener('click',function(event){
      wrappers.forEach(function(wrapper){
        if(!wrapper.contains(event.target)){
          wrapper.classList.remove('is-open');
          var trigger=wrapper.querySelector('.km-cat-menu-trigger');
          if(trigger) trigger.setAttribute('aria-expanded','false');
        }
      });
    });
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();
