/* Kharidino PWA worker: caches public static assets only. Never cache API, auth, or HTML responses. */
const CACHE_NAME = 'kharidino-pwa-static-v1';
const OFFLINE_URL = '/static/offline.html';
const STATIC_CORE = ['/static/icons/icon-192.svg','/static/manifest.webmanifest','/static/css/style.css','/static/css/pro.css',OFFLINE_URL];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(STATIC_CORE.map(u=>new Request(u,{cache:'reload'}))).catch(()=>{})));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('kharidino-pwa-')&&k!==CACHE_NAME).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
 const req=event.request;if(req.method!=='GET')return;
 const url=new URL(req.url);if(url.origin!==self.location.origin)return;
 // Exclude API, auth, administrative, and personalized HTML from caching.
 if(url.pathname.startsWith('/api/')||url.pathname.startsWith('/admin')||url.pathname.startsWith('/login')||url.pathname.startsWith('/logout')||url.pathname.startsWith('/register')||url.pathname.startsWith('/account'))return;
 if(url.pathname.startsWith('/static/')){
  event.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(res=>{if(res.ok&&res.type==='basic'){const copy=res.clone();caches.open(CACHE_NAME).then(c=>c.put(req,copy)).catch(()=>{});}return res;}).catch(()=>hit||Response.error())));
  return;
 }
 if(req.mode==='navigate'){
  event.respondWith(fetch(req).catch(()=>caches.match(OFFLINE_URL).then(r=>r||new Response('اتصال اینترنت برقرار نیست.',{status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}}))));
 }
});
