(() => {
  const $ = (s) => document.querySelector(s);
  const json = async (url, options = {}) => {
    const r = await fetch(url, options);
    const text = await r.text();
    let data;
    try { data = JSON.parse(text); } catch (_) { throw new Error(`پاسخ نامعتبر از سرور (${r.status})`); }
    if (!r.ok) throw new Error(data.message || data.error || 'خطا در درخواست');
    return data;
  };
  const escapeHtml = (s) => String(s ?? '').replace(/[&<>\'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

  async function loadStats() {
    try {
      const d = await json('/admin/kharidino-ai/api/stats');
      $('#products').textContent = d.products;
      $('#stores').textContent = d.stores;
      $('#offers').textContent = d.offers;
      $('#missingImages').textContent = d.missing_images;
    } catch (e) { console.warn(e); }
  }

  async function health() {
    try {
      const d = await json('/admin/kharidino-ai/api/health');
      $('#healthScore').textContent = d.score;
      $('#healthList').innerHTML = d.checks.map(x => `<div class="health-row ${escapeHtml(x.status)}"><span>${escapeHtml(x.name)}</span><small>${escapeHtml(x.detail)}</small><b>${x.status === 'ok' ? '✅' : x.status === 'warning' ? '⚠️' : '🔴'}</b></div>`).join('');
      loadStats();
    } catch (e) { $('#healthList').innerHTML = `<div class="kai-note">❌ ${escapeHtml(e.message)}</div>`; }
  }

  $('#refreshHealth')?.addEventListener('click', health);
  $('#backupBtn')?.addEventListener('click', async () => {
    const b = $('#backupResult'); b.textContent = 'در حال ساخت Snapshot...';
    try { const d = await json('/admin/kharidino-ai/api/backup', {method:'POST'}); b.textContent = `✅ Snapshot ساخته شد: ${d.snapshot}`; }
    catch (e) { b.textContent = `❌ ${e.message}`; }
  });

  $('#runAgent')?.addEventListener('click', async () => {
    const command = $('#command').value.trim();
    const box = $('#agentResult');
    if (!command) { box.classList.remove('hidden'); box.textContent = 'یک دستور وارد کن داداش 😄'; return; }
    box.classList.remove('hidden'); box.textContent = '🧠 در حال بررسی واقعی سایت و تحلیل دستور...';
    try {
      const d = await json('/admin/kharidino-ai/api/agent', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({command})});
      const plan = Array.isArray(d.plan) ? d.plan : [];
      box.innerHTML = `<b>🤖 تحلیل Kharidino AI آماده است</b><p><b>اولویت:</b> ${escapeHtml(d.priority || 'medium')}</p>${d.diagnosis ? `<p><b>🔎 تشخیص:</b> ${escapeHtml(d.diagnosis)}</p>` : ''}<p>${escapeHtml(d.message || '')}</p>${plan.length ? `<ol>${plan.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ol>` : ''}<div class="kai-note">🛡️ این مرحله فقط تحلیل و برنامه‌ریزی است؛ بدون تأیید مدیر هیچ فایل یا دیتابیسی تغییر نمی‌کند.</div>${d.model ? `<small>مدل: ${escapeHtml(d.model)}</small>` : ''}`;
    } catch (e) { box.textContent = `❌ ${e.message}`; }
  });

  const voice = $('#voiceBtn');
  if (voice && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR(); rec.lang = 'fa-IR'; rec.interimResults = false; rec.continuous = false;
    rec.onstart = () => voice.classList.add('active'); rec.onend = () => voice.classList.remove('active'); rec.onerror = () => voice.classList.remove('active');
    rec.onresult = e => { $('#command').value = (e.results[0][0].transcript || '').trim(); };
    voice.addEventListener('click', () => rec.start());
  } else if (voice) { voice.addEventListener('click', () => alert('برای فرمان صوتی فارسی از Chrome یا Edge استفاده کن.')); }

  health();
})();
