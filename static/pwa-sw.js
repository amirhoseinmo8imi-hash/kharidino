/* Kharidino PWA worker v2. Public static caching only; private data and commerce actions excluded. */
const CACHE='kharidino-pwa-static-v2',OFFLINE='/static/offline.html';
const CORE=[OFFLINE,'/static/manifest.webmanifest','/static/icons/icon-192.svg','/static/icons/icon-512.svg','/static/css/style.css','/static/css/pro.css','/static/js/main.js','/static/js/kharidino-pwa.js','/static/css/kharidino-pwa.css'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(CORE.map(x=>new Request(x,{cache:'reload'}))).catch(()=>{})));self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('kharidino-pwa-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{const r=e.request;if(r.method!=='GET')return;const u=new URL(r.url);if(u.origin!==self.location.origin)return;
if(/^\/(api\/|admin|login|logout|register|account|cart|checkout|payment|orders)/.test(u.pathname))return;
if(u.pathname.startsWith('/static/')){e.respondWith(caches.match(r).then(hit=>hit||fetch(r).then(res=>{if(res.ok&&res.type==='basic')caches.open(CACHE).then(c=>c.put(r,res.clone())).catch(()=>{});return res}).catch(()=>hit||Response.error())));return}
if(r.mode==='navigate')e.respondWith(fetch(r).catch(()=>caches.match(OFFLINE).then(x=>x||new Response('بدون اینترنت',{status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}})));
});
