(() => {
  const mapNode = document.getElementById('storeDirectoryMap');
  if (!mapNode || !window.L) return;
  const map = L.map(mapNode, { scrollWheelZoom: true }).setView([32.2, 53.6], 5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);
  const markers = L.featureGroup().addTo(map);
  const search = document.getElementById('storeMapSearch');
  const results = document.getElementById('storeMapResults');
  const count = document.getElementById('storeMapCount');
  let stores = [];
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const render = () => {
    const q = (search.value || '').trim().toLocaleLowerCase();
    const visible = stores.filter(s => !q || (s.name + ' ' + s.address).toLocaleLowerCase().includes(q));
    markers.clearLayers();
    results.replaceChildren();
    count.textContent = visible.length + ' فروشگاه روی نقشه';
    if (!visible.length) {
      const empty = document.createElement('p'); empty.className = 'km-map-empty';
      empty.textContent = stores.length ? 'نتیجه‌ای برای این جستجو پیدا نشد.' : 'هنوز موقعیت مکانی برای فروشگاه‌ها ثبت نشده است.';
      results.appendChild(empty); return;
    }
    visible.forEach(store => {
      const marker = L.marker([store.latitude, store.longitude]).addTo(markers);
      const popup = '<strong>' + escapeHtml(store.name) + '</strong><br>' + escapeHtml(store.address) + '<br><a href="' + escapeHtml(store.url) + '">مشاهده ویترین</a>';
      marker.bindPopup(popup);
      const card = document.createElement('article'); card.className = 'km-map-store';
      const title = document.createElement('strong'); title.textContent = store.name;
      const address = document.createElement('span'); address.textContent = store.address || 'نشانی ثبت نشده';
      const link = document.createElement('a'); link.href = store.url; link.textContent = 'مشاهده ویترین';
      card.append(title, address, link);
      card.addEventListener('click', () => { map.setView([store.latitude, store.longitude], 15); marker.openPopup(); });
      results.appendChild(card);
    });
    if (!q && markers.getLayers().length) map.fitBounds(markers.getBounds().pad(0.18), { maxZoom: 13 });
  };
  fetch('/api/map/stores', { headers: { Accept: 'application/json' }, cache: 'no-store' })
    .then(response => { if (!response.ok) throw new Error('map data unavailable'); return response.json(); })
    .then(data => { stores = Array.isArray(data.stores) ? data.stores : []; render(); })
    .catch(() => { count.textContent = 'دریافت اطلاعات نقشه ناموفق بود'; results.textContent = 'لطفاً کمی بعد دوباره تلاش کن.'; });
  search.addEventListener('input', render);
  document.getElementById('storeMapLocate').addEventListener('click', () => {
    if (!navigator.geolocation) { count.textContent = 'مکان‌یابی در این مرورگر پشتیبانی نمی‌شود'; return; }
    navigator.geolocation.getCurrentPosition(position => {
      const point = [position.coords.latitude, position.coords.longitude];
      L.circleMarker(point, { radius: 9, color: '#2563eb', fillOpacity: .7 }).addTo(map).bindPopup('موقعیت فعلی شما').openPopup();
      map.setView(point, 14);
    }, () => { count.textContent = 'دسترسی به موقعیت داده نشد'; }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 });
  });
})();
