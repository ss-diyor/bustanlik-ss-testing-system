const state = { student:null, stats:null, results:[], classmates:[], config:null, mock:null };
const page = location.pathname.split('/').filter(Boolean)[1] || 'home';
const titles = {
  home:['O‘QUVCHI KABINETI','Bosh sahifa'], dtm:['NATIJALAR','DTM natijalar'],
  mock:['NATIJALAR','Mock natijalar'], ranking:['STATISTIKA','Reyting va sinfdoshlar'],
  learning:['TA’LIM','O‘qish va testlar'], services:['SOZLAMALAR','Xizmatlar']
};
const esc = value => String(value ?? '—').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const fmt = value => value == null ? '—' : (Number.isInteger(Number(value)) ? String(value) : Number(value).toFixed(1));

document.addEventListener('DOMContentLoaded', init);

async function init(){
  const safePage = titles[page] ? page : 'home';
  document.querySelectorAll(`[data-page="${safePage}"]`).forEach(a => a.classList.add('active'));
  document.getElementById('pageEyebrow').textContent = titles[safePage][0];
  document.getElementById('pageTitle').textContent = titles[safePage][1];
  document.title = `${titles[safePage][1]} — Bustanlik SS`;
  document.getElementById('logoutButton').onclick = logout;
  try{
    const response = await fetch('/api/student',{cache:'no-store'});
    if(response.status === 401){ location.href='/mock'; return; }
    if(!response.ok) throw new Error((await response.json()).error || 'Ma’lumot yuklanmadi');
    Object.assign(state, await response.json());
    fillIdentity();
    await render(safePage);
    document.getElementById('pageLoader').hidden=true;
    document.getElementById('pageContent').hidden=false;
  }catch(error){ showError(error.message); }
}

function initials(name){return String(name||'O').split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase()}
function fillIdentity(){
  document.getElementById('sideAvatar').textContent=initials(state.student.ismlar);
  document.getElementById('sideName').textContent=state.student.ismlar;
  document.getElementById('sideCode').textContent=state.student.kod;
}
async function logout(){await fetch('/api/mock/logout',{method:'POST'});location.href='/mock'}
function showError(message){document.getElementById('pageLoader').hidden=true;document.getElementById('pageContent').hidden=true;document.getElementById('pageErrorText').textContent=message;document.getElementById('pageError').hidden=false}
async function render(target){
  if(target==='home') renderHome();
  if(target==='dtm') renderDtm();
  if(target==='mock') await renderMock();
  if(target==='ranking') renderRanking();
  if(target==='learning') await renderLearning();
  if(target==='services') renderServices();
}
function hero(){return `<section class="hero"><div><div class="kicker">XUSH KELIBSIZ</div><h2>${esc(state.student.ismlar)}</h2><p>${esc(state.student.maktab)} · ${esc(state.student.sinf)} · ${esc(state.student.yonalish)} · Kod: ${esc(state.student.kod)}</p></div><div class="hero-avatar">${initials(state.student.ismlar)}</div></section>`}
function metrics(){const rank=state.stats.sinf_rank&&state.stats.sinf_rank!=='—'?`${esc(state.stats.sinf_rank)}-o‘rin`:'—';return `<div class="metric-grid"><div class="metric-card"><small>Oxirgi ball</small><strong>${fmt(state.stats.last)}</strong></div><div class="metric-card"><small>Eng yuqori</small><strong>${fmt(state.stats.best)}</strong></div><div class="metric-card"><small>O‘rtacha</small><strong>${fmt(state.stats.avg)}</strong></div><div class="metric-card"><small>Sinf o‘rni</small><strong>${rank}</strong></div></div>`}
function renderHome(){
  const latest=[...state.results].reverse().slice(0,3);
  document.getElementById('pageContent').innerHTML=hero()+metrics()+`<div class="section-head"><h2>Asosiy bo‘limlar</h2><p>TEZKOR KIRISH</p></div><div class="action-grid"><a class="action-card" href="/cabinet/dtm"><div class="icon">▥</div><h3>DTM natijalar</h3><p>Natijalar dinamikasi va barcha urinishlar.</p></a><a class="action-card" href="/cabinet/mock"><div class="icon">◎</div><h3>Mock natijalar</h3><p>IELTS, Milliy sertifikat va boshqa mocklar.</p></a><a class="action-card" href="/mock/home"><div class="icon">＋</div><h3>Test ishlash</h3><p>Faol mock imtihonlarni boshlang yoki davom ettiring.</p></a></div><div class="section-head"><h2>Oxirgi DTM natijalar</h2><p>${state.results.length} TA NATIJA</p></div><div class="result-list">${latest.length?latest.map(dtmCard).join(''):'<div class="panel empty">Hali DTM natijasi mavjud emas.</div>'}</div>`;
}
function dtmCard(r){return `<article class="result-card"><div><h3>DTM imtihoni</h3><p>${esc(r.sana)} · Majburiy: ${fmt(r.majburiy)} · 1-asosiy: ${fmt(r.asosiy_1)} · 2-asosiy: ${fmt(r.asosiy_2)}</p></div><div class="score">${fmt(r.umumiy_ball)}</div></article>`}
function renderDtm(){
  const list=[...state.results].reverse();
  document.getElementById('pageContent').innerHTML=`${metrics()}<div class="section-head"><h2>Barcha DTM natijalari</h2><p>${list.length} TA URINISH</p></div><div class="result-list">${list.length?list.map(dtmCard).join(''):'<div class="panel empty">Hali DTM natijasi yo‘q.</div>'}</div>`;
}
async function getMock(){if(state.mock)return state.mock;const r=await fetch('/api/student/mock',{cache:'no-store'});if(!r.ok)throw new Error('Mock natijalari yuklanmadi');state.mock=(await r.json()).mock_results||[];return state.mock}
async function renderMock(){
  const list=await getMock();
  const types=[...new Map(list.map(r=>[r.exam_key,r.exam_label||r.exam_key])).entries()];
  document.getElementById('pageContent').innerHTML=`<div class="metric-grid"><div class="metric-card"><small>Jami urinish</small><strong>${list.length}</strong></div><div class="metric-card"><small>Imtihon turi</small><strong>${types.length}</strong></div><div class="metric-card"><small>Oxirgi ball</small><strong>${fmt(list[0]?.umumiy_ball)}</strong></div><div class="metric-card"><small>Oxirgi sana</small><strong style="font-size:17px">${esc(list[0]?.test_sanasi)}</strong></div></div><div class="section-head"><h2>Mock imtihonlar</h2><p>FAN BO‘YICHA FILTR</p></div><div class="filter-row"><button class="active" data-filter="all">Barchasi</button>${types.map(([k,v])=>`<button data-filter="${esc(k)}">${esc(v)}</button>`).join('')}</div><div id="mockResults" class="result-list"></div>`;
  const draw=filter=>{const rows=filter==='all'?list:list.filter(r=>r.exam_key===filter);document.getElementById('mockResults').innerHTML=rows.length?rows.map(mockCard).join(''):'<div class="panel empty">Natijalar topilmadi.</div>'};
  draw('all');document.querySelectorAll('[data-filter]').forEach(btn=>btn.onclick=()=>{document.querySelectorAll('[data-filter]').forEach(x=>x.classList.remove('active'));btn.classList.add('active');draw(btn.dataset.filter)})
}
function mockCard(r){const level=r.level_label?`<span class="badge">${esc(r.level_label)}</span>`:'';return `<article class="result-card"><div><h3>${esc(r.exam_label||r.exam_key)} ${level}</h3><p>${esc(r.subject_name||'Fan ko‘rsatilmagan')} · ${esc(r.test_sanasi)}</p></div><div class="score">${fmt(r.umumiy_ball)}</div></article>`}
function renderRanking(){
  const classmates=state.classmates||[];
  document.getElementById('pageContent').innerHTML=`${metrics()}<div class="page-grid" style="margin-top:17px"><section class="panel"><h2>Sinfdoshlar</h2><div class="classmate-list">${classmates.length?classmates.map((c,i)=>`<div class="classmate"><b>${i+1}.</b> ${esc(c.ismlar)}</div>`).join(''):'<div class="empty">Sinfdoshlar topilmadi.</div>'}</div></section><aside class="panel"><h2>Profil</h2><div class="profile-lines"><div class="profile-line"><span>O‘quvchi</span><b>${esc(state.student.ismlar)}</b></div><div class="profile-line"><span>Maktab</span><b>${esc(state.student.maktab)}</b></div><div class="profile-line"><span>Sinf</span><b>${esc(state.student.sinf)}</b></div><div class="profile-line"><span>Yo‘nalish</span><b>${esc(state.student.yonalish)}</b></div></div></aside></div>`;
}
async function renderLearning(){
  const [scheduleResponse,materialsResponse]=await Promise.all([fetch('/api/schedule'),fetch('/api/materials')]);
  const schedule=(await scheduleResponse.json()).schedule||[];const materials=(await materialsResponse.json()).materials||[];
  document.getElementById('pageContent').innerHTML=`<div class="learning-grid"><article class="learning-card"><h3>◎ Mock testlar</h3><p>Faol testlarni ishlang, tugallanmagan urinishni davom ettiring.</p><a class="primary-link" href="/mock/home">Testlar sahifasi →</a></article><article class="learning-card"><h3>◇ O‘quv materiallari</h3><p>${materials.length} ta material kabinetda mavjud.</p></article><article class="learning-card"><h3>▤ Testlar taqvimi</h3><p>${schedule.length?schedule.slice(0,3).map(x=>`${esc(x.sana)} — ${esc(x.test_nomi)}`).join('<br>'):'Yaqin testlar rejalashtirilmagan.'}</p></article><article class="learning-card"><h3>▧ Quiz va mini-test</h3><p>Botdagi mashq quizlari va mini-testlar keyingi integratsiya bosqichida shu yerda ishlaydi.</p></article></div>`;
}
function renderServices(){
  document.getElementById('pageContent').innerHTML=`<div class="service-grid"><button class="service-button" data-service="qr"><span>▦</span><b>Mening QR-kodim</b><small>Davomat uchun shaxsiy QR</small></button><button class="service-button" data-service="notifications"><span>◉</span><b>Bildirishnomalar</b><small>Xabar turlarini sozlash</small></button><button class="service-button" data-service="contact"><span>✎</span><b>Admin bilan bog‘lanish</b><small>Murojaat yuborish</small></button><button class="service-button" data-service="profile"><span>◌</span><b>Shaxsiy profil</b><small>Kabinet ma’lumotlari</small></button><div id="serviceDetail" class="service-detail"><div class="empty">Kerakli xizmatni tanlang.</div></div></div>`;
  document.querySelectorAll('[data-service]').forEach(btn=>btn.onclick=()=>openService(btn.dataset.service));
}
async function openService(service){
  const box=document.getElementById('serviceDetail');
  if(service==='qr'){box.innerHTML=`<h3>Mening QR-kodim</h3><p>Davomatdan o‘tishda ushbu QR-kodni ko‘rsating.</p><img src="/api/student/qr?ts=${Date.now()}" alt="Shaxsiy QR-kod">`}
  if(service==='profile'){box.innerHTML=`<h3>Shaxsiy profil</h3><div class="profile-lines"><div class="profile-line"><span>Ism</span><b>${esc(state.student.ismlar)}</b></div><div class="profile-line"><span>Kod</span><b>${esc(state.student.kod)}</b></div><div class="profile-line"><span>Maktab</span><b>${esc(state.student.maktab)}</b></div><div class="profile-line"><span>Sinf</span><b>${esc(state.student.sinf)}</b></div><div class="profile-line"><span>Yo‘nalish</span><b>${esc(state.student.yonalish)}</b></div></div>`}
  if(service==='notifications')await renderNotifications(box);
  if(service==='contact')renderContact(box);
}
async function renderNotifications(box){
  box.innerHTML='<p>Sozlamalar yuklanmoqda...</p>';const response=await fetch('/api/student/notifications');const data=await response.json();const labels={notify_results:'DTM natijalari',notify_mock_results:'Mock natijalari',notify_admin_messages:'Admin xabarlari',notify_reminders:'Eslatmalar'};box.innerHTML=`<h3>Bildirishnomalar</h3>${Object.entries(labels).map(([key,label])=>`<label class="toggle-row"><span>${label}</span><input data-notification="${key}" type="checkbox" ${data.settings?.[key]!==false?'checked':''}></label>`).join('')}`;document.querySelectorAll('[data-notification]').forEach(input=>input.onchange=()=>fetch('/api/student/notifications',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:input.dataset.notification,enabled:input.checked})}))
}
function renderContact(box){box.innerHTML=`<h3>Admin bilan bog‘lanish</h3><textarea id="contactText" maxlength="2000" placeholder="Murojaatingizni yozing..."></textarea><button id="contactSend">Yuborish</button><p id="contactStatus"></p>`;document.getElementById('contactSend').onclick=async()=>{const text=document.getElementById('contactText').value.trim(),status=document.getElementById('contactStatus');if(!text){status.textContent='Murojaat matnini yozing.';return}const r=await fetch('/api/student/contact-admin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});const d=await r.json();status.textContent=r.ok?'Murojaatingiz adminga yuborildi.':(d.error||'Xatolik yuz berdi.');if(r.ok)document.getElementById('contactText').value=''} }
