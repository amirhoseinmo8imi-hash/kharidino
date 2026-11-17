(() => {
  const node = document.getElementById('sellerLocationPicker');
  if (!node || !window.L) return;
  const latInput = document.getElementById('storeLatitude');
  const lonInput = document.getElementById('storeLongitude');
  const initialLat = Number(latInput.value), initialLon = Number(lonInput.value);
  const hasPoint = latInput.value.trim() !== '' && lonInput.value.trim() !== '';
  const map = L.map(node).setView(hasPoint ? [initialLat, initialLon] : [32.2, 53.6], hasPoint ? 14 : 5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
  let marker = hasPoint ? L.marker([initialLat, initialLon]).addTo(map) : null;
  map.on('click', event => {
    const { lat, lng } = event.latlng;
    latInput.value = lat.toFixed(7); lonInput.value = lng.toFixed(7);
    if (marker) marker.setLatLng(event.latlng); else marker = L.marker(event.latlng).addTo(map);
  });
})();
