/* Kharidino theme controller — 2026 */
(function(){
  'use strict';
  var KEY='kharidino-theme';
  var root=document.body;
  if(!root)return;
  function preferred(){return window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}
  function apply(mode){
    var dark=mode==='dark';
    root.classList.toggle('kh-modern-dark',dark);
    root.setAttribute('data-theme',dark?'dark':'light');
    var b=document.querySelector('[data-theme-toggle]');
    if(b){
      b.setAttribute('aria-pressed',dark?'true':'false');
      b.setAttribute('aria-label',dark?'فعال‌کردن حالت روشن':'فعال‌کردن حالت تاریک');
      b.title=dark?'حالت روشن':'حالت تاریک';
    }
  }
  var saved=localStorage.getItem(KEY);
  apply(saved==='dark'||saved==='light'?saved:preferred());
  document.addEventListener('click',function(e){
    var b=e.target.closest&&e.target.closest('[data-theme-toggle]');
    if(!b)return;
    var next=root.classList.contains('kh-modern-dark')?'light':'dark';
    localStorage.setItem(KEY,next); apply(next);
  });
})();
