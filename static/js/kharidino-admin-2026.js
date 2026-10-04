/* Kharidino Admin Command Center 2026 */
(function(){
  'use strict';
  const body=document.body;
  if(!body.classList.contains('kh-admin-page')) return;

  const sidebar=document.querySelector('.admin-sidebar');
  const backdrop=document.querySelector('[data-admin-backdrop]');
  const collapse=document.querySelector('[data-admin-collapse]');
  const mobileMenu=document.querySelector('[data-admin-mobile-menu]');
  const theme=document.querySelector('[data-admin-theme]');
  const searchToggle=document.querySelector('[data-admin-search-toggle]');
  const searchPanel=document.querySelector('[data-admin-search-panel]');
  const searchInput=document.querySelector('[data-admin-search-input]');
  const results=document.querySelector('[data-admin-search-results]');
  const breadcrumb=document.querySelector('[data-admin-breadcrumb]');

  function closeMobile(){ if(sidebar) sidebar.classList.remove('is-mobile-open'); if(backdrop) backdrop.classList.remove('is-visible'); }
  if(mobileMenu) mobileMenu.addEventListener('click',function(){ if(sidebar) sidebar.classList.add('is-mobile-open'); if(backdrop) backdrop.classList.add('is-visible'); });
  if(backdrop) backdrop.addEventListener('click',closeMobile);

  if(collapse) collapse.addEventListener('click',function(){
    if(window.innerWidth<=860){ closeMobile(); return; }
    sidebar.classList.toggle('is-collapsed');
    const layout=document.querySelector('.admin-layout');
    if(layout) layout.style.gridTemplateColumns=sidebar.classList.contains('is-collapsed')?'86px minmax(0,1fr)':'292px minmax(0,1fr)';
    localStorage.setItem('kharidino-admin-collapsed',sidebar.classList.contains('is-collapsed')?'1':'0');
  });
  if(localStorage.getItem('kharidino-admin-collapsed')==='1' && window.innerWidth>860 && sidebar){
    sidebar.classList.add('is-collapsed');
    const layout=document.querySelector('.admin-layout');
    if(layout) layout.style.gridTemplateColumns='86px minmax(0,1fr)';
  }

  const navLinks=[...document.querySelectorAll('[data-admin-target]')];
  const sections=[...document.querySelectorAll('.admin-section[id]')];
  const labels={dashboard:'داشبورد', 'orders-admin':'سفارش‌ها','products-admin':'محصولات','offers-admin':'قیمت و پیشنهادها','categories-admin':'دسته‌بندی‌ها','stores-admin':'فروشگاه‌ها','users-admin':'کاربران','invoices-admin':'فاکتورها','appearance-admin':'ظاهر و رسانه','settings':'تنظیمات'};
  function activate(id,scroll){
    navLinks.forEach(a=>a.classList.toggle('is-active',a.dataset.adminTarget===id));
    if(breadcrumb) breadcrumb.textContent=labels[id]||'مدیریت';
    if(scroll){const el=document.getElementById(id); if(el) el.scrollIntoView({behavior:'smooth',block:'start'});}
    closeMobile();
  }
  navLinks.forEach(a=>a.addEventListener('click',function(e){
    const id=this.dataset.adminTarget;
    if(!document.getElementById(id)) return;
    e.preventDefault(); activate(id,true); history.replaceState(null,'','#'+id);
  }));
  const observer=new IntersectionObserver(entries=>{
    const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>b.intersectionRatio-a.intersectionRatio)[0];
    if(visible) activate(visible.target.id,false);
  },{rootMargin:'-18% 0px -65% 0px',threshold:[.05,.25,.5]});
  sections.forEach(s=>observer.observe(s));

  function openSearch(){if(!searchPanel)return;searchPanel.hidden=false;setTimeout(()=>searchInput&&searchInput.focus(),20)}
  function closeSearch(){if(searchPanel)searchPanel.hidden=true}
  if(searchToggle) searchToggle.addEventListener('click',()=>searchPanel&&searchPanel.hidden?openSearch():closeSearch());
  document.addEventListener('keydown',function(e){
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openSearch();}
    if(e.key==='Escape'){closeSearch();closeMobile();}
  });
  if(searchInput){
    const index=[];
    sections.forEach(section=>{
      const title=section.querySelector('h1,h2,h3');
      if(title) index.push({id:section.id,title:title.textContent.trim(),text:section.textContent.replace(/\s+/g,' ').trim()});
    });
    searchInput.addEventListener('input',function(){
      const q=this.value.trim().toLowerCase();
      if(!q){results.innerHTML='<div class="admin-search-result"><i class="fa-solid fa-lightbulb"></i><span>برای رفتن سریع، نام بخش یا کاری مثل «سفارش» یا «محصول» را بنویس.</span></div>';return;}
      const found=index.filter(x=>(x.title+' '+x.text).toLowerCase().includes(q)).slice(0,8);
      results.innerHTML=found.length?found.map(x=>'<a class="admin-search-result" href="#'+x.id+'" data-result-id="'+x.id+'"><i class="fa-solid fa-arrow-left"></i><span>'+x.title+'</span><small>رفتن به بخش</small></a>').join(''):'<div class="admin-search-result"><i class="fa-solid fa-circle-info"></i><span>نتیجه‌ای پیدا نشد.</span></div>';
      results.querySelectorAll('[data-result-id]').forEach(a=>a.addEventListener('click',function(e){e.preventDefault();activate(this.dataset.resultId,true);history.replaceState(null,'','#'+this.dataset.resultId);closeSearch();}));
    });
  }

  if(theme){
    if(localStorage.getItem('kharidino-admin-theme')==='dim') body.classList.add('admin-dim');
    theme.addEventListener('click',function(){
      body.classList.toggle('admin-dim');
      localStorage.setItem('kharidino-admin-theme',body.classList.contains('admin-dim')?'dim':'light');
      const icon=this.querySelector('i'); if(icon) icon.className=body.classList.contains('admin-dim')?'fa-solid fa-sun':'fa-solid fa-moon';
    });
  }

  document.querySelectorAll('.admin-nav a[href^="#"]').forEach(a=>a.addEventListener('keydown',e=>{if(e.key==='Enter')a.click();}));
})();
