/* Kharidino PWA worker: public static resources only. Never cache private pages or actions. */
const CACHE='kharidino-pwa-static-v3';
const OFFLINE='/static/offline.html';
const CORE=[OFFLINE,'/static/manifest.webmanifest','/static/icons/icon-192.svg','/static/icons/icon-512.svg','/static/js/kharidino-pwa.js','/static/css/kharidino-pwa.css'];
const PRIVATE=/^\/(?:api(?:\/|$)|admin(?:\/|$)|login(?:\/|$)|logout(?:\/|$)|register(?:\/|$)|account(?:\/|$)|cart(?:\/|$)|checkout(?:\/|$)|payment(?:\/|$)|orders(?:\/|$)|profile(?:\/|$)|seller(?:\/|$)|messages(?:\/|$))/i;
self.addEventListener('install',event=>{event.waitUntil((async()=>{const cache=await caches.open(CACHE);await Promise.all(CORE.map(async path=>{try{const response=await fetch(path,{cache:'reload'});if(response.ok)await cache.put(path,response)}catch(_){}}));await self.skipWaiting()})())});
self.addEventListener('activate',event=>{event.waitUntil((async()=>{const keys=await caches.keys();await Promise.all(keys.filter(key=>key.startsWith('kharidino-pwa-')&&key!==CACHE).map(key=>caches.delete(key)));await self.clients.claim()})())});
self.addEventListener('fetch',event=>{const request=event.request;if(request.method!=='GET')return;const url=new URL(request.url);if(url.origin!==self.location.origin||PRIVATE.test(url.pathname))return;
if(url.pathname.startsWith('/static/')){event.respondWith((async()=>{const cache=await caches.open(CACHE);const cached=await cache.match(request);if(cached)return cached;try{const response=await fetch(request);if(response.ok&&response.type==='basic')await cache.put(request,response.clone());return response}catch(_){return cached||Response.error()}})());return}
if(request.mode==='navigate'){event.respondWith((async()=>{try{return await fetch(request)}catch(_){const cache=await caches.open(CACHE);return await cache.match(OFFLINE)||new Response('در حال حاضر آفلاین هستید',{status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}})}})())}
});
