const CACHE='kharidino-v1';
const CORE=['/','/static/css/style.css','/static/css/pro.css','/static/js/main.js'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(CORE).catch(()=>{}))));
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(caches.match(e.request).then(c=>c||fetch(e.request).then(r=>{const copy=r.clone();caches.open(CACHE).then(x=>x.put(e.request,copy)).catch(()=>{});return r}).catch(()=>c)))});
