/* Kharidino animated background controller */
(function(){
  'use strict';
  function init(){
    const root=document.querySelector('.site-background');
    if(!root) return;
    const media=root.querySelector('.site-background-media');
    if(media && media.tagName==='VIDEO'){
      media.muted=true;
      media.loop=true;
      media.playsInline=true;
      const play=()=>media.play().catch(()=>{});
      play();
      document.addEventListener('visibilitychange',()=>{
        if(document.hidden) media.pause(); else play();
      });
    }
    root.classList.add('background-ready');
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);
  else init();
})();
