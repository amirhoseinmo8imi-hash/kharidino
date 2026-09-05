(() => {
  const $ = (s) => document.querySelector(s);
  const json = async (url, options={}) => { const r = await fetch(url, options); const data = await r.json(); if (!r.ok) throw new Error(data.error || 'خطا'); return data; };

  async function loadStats(){
    try { const d=await json('/admin/kharidino-ai/api/stats'); $('#products').textContent=d.products; $('#stores').textContent=d.stores; $('#offers').textContent=d.offers; $('#missingImages').textContent=d.missing_images; } catch(e) {}
  }
  function renderHealth(d){
    $('#healthScore').textContent=d.score;
    $('#healthList').innerHTML=d.checks.map(x=>`<div class="health-row ${x.status}"><span>${escapeHtml(x.name)}</span><small>${escapeHtml(x.detail)}</small><b>${x.status==='ok'?'✅':x.status==='warning'?'⚠️':'🔴'}</b></div>`).join('');
  }
  async function health(){ try{ renderHealth(await json('/admin/kharidino-ai/api/health')); loadStats(); }catch(e){ $('#healthList').innerHTML='<div class="kai-note">خطا در بررسی سایت</div>'; } }
  function escapeHtml(s){ return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }

  $('#refreshHealth')?.addEventListener('click', health);
  $('#backupBtn')?.addEventListener('click', async()=>{
    const b=$('#backupResult'); b.textContent='در حال ساخت Snapshot...';
    try{ const d=await json('/admin/kharidino-ai/api/backup',{method:'POST'}); b.textContent=`✅ Snapshot ساخته شد: ${d.snapshot}`; }
    catch(e){ b.textContent=`❌ ${e.message}`; }
  });
  $('#runAgent')?.addEventListener('click', async()=>{
    const command=$('#command').value.trim(); const box=$('#agentResult');
    if(!command){ box.classList.remove('hidden'); box.textContent='یک دستور وارد کن داداش 😄'; return; }
    box.classList.remove('hidden'); box.textContent='در حال تحلیل...';
    try{ const d=await json('/admin/kharidino-ai/api/agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command})}); box.innerHTML=`<b>🧠 برنامه آماده است</b><p>${escapeHtml(d.message)}</p><ul>${d.plan.map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul>`; }
    catch(e){ box.textContent='❌ '+e.message; }
  });

  const voice=$('#voiceBtn');
  if(voice && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)){
    const SR=window.SpeechRecognition||window.webkitSpeechRecognition; const rec=new SR(); rec.lang='fa-IR'; rec.interimResults=false; rec.continuous=false;
    rec.onstart=()=>voice.classList.add('active'); rec.onend=()=>voice.classList.remove('active'); rec.onerror=()=>voice.classList.remove('active');
    rec.onresult=e=>{ $('#command').value=(e.results[0][0].transcript||'').trim(); };
    voice.addEventListener('click',()=>rec.start());
  } else if(voice){ voice.title='مرورگر شما Speech Recognition را پشتیبانی نمی‌کند'; voice.addEventListener('click',()=>alert('برای فرمان صوتی فارسی از Chrome یا Edge استفاده کن.')); }
  loadStats();
})();
