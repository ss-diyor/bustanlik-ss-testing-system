const state = { student:null, stats:null, results:[], classmates:[], config:null, mock:null };
const page = location.pathname.split('/').filter(Boolean)[1] || 'home';
const titles = {
  home:['O‘QUVCHI KABINETI','Bosh sahifa'], dtm:['NATIJALAR','DTM natijalar'],
  mock:['NATIJALAR','Mock natijalar'], ranking:['STATISTIKA','Sinf reytingi'],
  classroom:['SINF','Mening sinfim'],
  learning:['TA’LIM','O‘qish va testlar'], services:['SOZLAMALAR','Xizmatlar']
};
const esc = value => String(value ?? '—').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const safeUrl = value => {try{const url=new URL(String(value||''),location.origin);return ['http:','https:'].includes(url.protocol)?url.href:'#'}catch(error){return '#'}};
const fmt = value => value == null ? '—' : (Number.isInteger(Number(value)) ? String(value) : Number(value).toFixed(1));
const ICONS = {
  home:'<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9 21v-7h6v7"/>',
  chart:'<path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/>',
  target:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M22 12h-3"/>',
  trophy:'<path d="M8 4h8v4a4 4 0 0 1-8 0V4Z"/><path d="M8 6H4v1a4 4 0 0 0 4 4M16 6h4v1a4 4 0 0 1-4 4M12 12v5M8 21h8M9 17h6"/>',
  users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  book:'<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V4H6.5A2.5 2.5 0 0 0 4 6.5v13Z"/><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4"/>',
  settings:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21H9.6v-.1A1.7 1.7 0 0 0 8.5 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1H3v-4h1a1.7 1.7 0 0 0 .6-1 1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6V3h4v1a1.7 1.7 0 0 0 1 .6 1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9a1.7 1.7 0 0 0 .6 1h1v4h-1a1.7 1.7 0 0 0-.6 1Z"/>',
  logout:'<path d="M10 17l5-5-5-5M15 12H3"/><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>',
  play:'<path d="m8 5 11 7-11 7V5Z"/>', arrow:'<path d="M5 12h14M13 6l6 6-6 6"/>',
  certificate:'<path d="M6 3h12v18l-6-3-6 3V3Z"/><path d="M9 8h6M9 12h6"/>',
  chevronDown:'<path d="m6 9 6 6 6-6"/>', chevronUp:'<path d="m6 15 6-6 6 6"/>',
  download:'<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>', link:'<path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"/>',
  qr:'<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3h-3zM18 18h3v3h-3zM18 14h3M14 18v3"/>',
  bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  message:'<path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8Z"/>',
  user:'<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/>',
  file:'<path d="M6 2h9l5 5v15H6V2Z"/><path d="M14 2v6h6M9 13h6M9 17h6"/>',
  quiz:'<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.7 2.7 0 1 1 4.3 2.2c-1 .7-1.8 1.2-1.8 2.8M12 18h.01"/>',
  trend:'<path d="m3 17 6-6 4 4 8-9"/><path d="M15 6h6v6"/>'
};
function icon(name,className=''){return `<svg class="ui-icon ${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]||ICONS.quiz}</svg>`}
function hydrateIcons(){document.querySelectorAll('[data-icon]').forEach(node=>{node.innerHTML=icon(node.dataset.icon)})}

document.addEventListener('DOMContentLoaded', init);

async function init(){
  hydrateIcons();
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
  if(target==='classroom') renderClassroom();
  if(target==='learning') await renderLearning();
  if(target==='services') renderServices();
}
function hero(){return `<section class="hero dashboard-hero"><div class="hero-copy"><div class="kicker">XUSH KELIBSIZ</div><h2>${esc(state.student.ismlar)}</h2><div class="hero-meta"><span>${icon('users')}${esc(state.student.sinf)}</span><span>${icon('book')}${esc(state.student.yonalish)}</span><span>${icon('certificate')}${esc(state.student.kod)}</span></div><p>${esc(state.student.maktab)}</p></div><div class="hero-profile"><div class="hero-avatar">${initials(state.student.ismlar)}</div><span>O‘quvchi profili</span></div></section>`}
function metrics(){const rank=state.stats.sinf_rank&&state.stats.sinf_rank!=='—'?`${esc(state.stats.sinf_rank)}-o‘rin`:'—';const items=[['trend','Oxirgi ball',fmt(state.stats.last)],['trophy','Eng yuqori',fmt(state.stats.best)],['chart','O‘rtacha',fmt(state.stats.avg)],['users','Sinf o‘rni',rank]];return `<div class="metric-grid">${items.map(([name,label,value])=>`<div class="metric-card"><div class="metric-icon">${icon(name)}</div><div><small>${label}</small><strong>${value}</strong></div></div>`).join('')}</div>`}
function renderHome(){
  const latest=[...state.results].reverse().slice(0,3);
  const actions=[['chart','DTM natijalar','Natijalar dinamikasi va barcha urinishlar.','/cabinet/dtm'],['target','Mock natijalar','Mock hisobotlari va tasdiqlash sahifalari.','/cabinet/mock'],['users','Mening sinfim','Sinfdoshlaringiz ro‘yxatini ko‘ring.','/cabinet/classroom'],['play','Test ishlash','Faol mock imtihonni boshlang yoki davom ettiring.','/mock/home']];
  document.getElementById('pageContent').innerHTML=hero()+metrics()+`<div class="section-head"><div><p>TEZKOR KIRISH</p><h2>Asosiy bo‘limlar</h2></div><span>KABINET IMKONIYATLARI</span></div><div class="action-grid dashboard-actions">${actions.map(([name,title,copy,href])=>`<a class="action-card" href="${href}"><div class="icon">${icon(name)}</div><div><h3>${title}</h3><p>${copy}</p></div><span class="action-arrow">${icon('arrow')}</span></a>`).join('')}</div><div class="section-head"><div><p>SO‘NGGI FAOLLIK</p><h2>Oxirgi DTM natijalar</h2></div><span>${state.results.length} TA NATIJA</span></div><div class="result-list dashboard-results">${latest.length?latest.map(dtmCompactCard).join(''):'<div class="panel empty">Hali DTM natijasi mavjud emas.</div>'}</div>`;
}
function dtmCompactCard(r){return `<article class="result-card"><div class="result-leading">${icon('chart')}<div><h3>DTM imtihoni</h3><p>${esc(r.sana)} · Majburiy: ${fmt(r.majburiy)} · 1-asosiy: ${fmt(r.asosiy_1)} · 2-asosiy: ${fmt(r.asosiy_2)}</p></div></div><div class="score">${fmt(r.umumiy_ball)}<small>/ 189</small></div></article>`}
function subjectScore(correct, coefficient){return Number(correct||0)*Number(coefficient||0)}
function dtmTrendChart(list){
  if(!list.length)return '<div class="empty">Grafik uchun natija mavjud emas.</div>';
  const width=760,height=210,padX=34,padY=28,usableW=width-padX*2,usableH=height-padY*2;
  const points=list.map((r,i)=>{const x=list.length===1?width/2:padX+(i/(list.length-1))*usableW;const y=padY+(1-Math.min(189,Number(r.umumiy_ball||0))/189)*usableH;return {x,y,r}});
  const guides=[0,63,126,189].map(value=>{const y=padY+(1-value/189)*usableH;return `<line x1="${padX}" y1="${y}" x2="${width-padX}" y2="${y}"/><text x="2" y="${y+4}">${value}</text>`}).join('');
  const dots=points.map((p,i)=>`<circle cx="${p.x}" cy="${p.y}" r="5"><title>${esc(p.r.sana)} — ${fmt(p.r.umumiy_ball)} ball</title></circle>${(i===0||i===points.length-1)?`<text class="chart-date" x="${p.x}" y="${height-5}" text-anchor="${i===0?'start':'end'}">${esc(p.r.sana)}</text>`:''}`).join('');
  return `<div class="dtm-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="DTM ballari dinamikasi"><g class="chart-guides">${guides}</g><polyline points="${points.map(p=>`${p.x},${p.y}`).join(' ')}"/><g class="chart-dots">${dots}</g></svg></div>`;
}
function dtmSubject(label,correct,coefficient,color){const score=subjectScore(correct,coefficient);return `<div class="dtm-subject"><div class="subject-head"><span>${label}</span><b>${fmt(correct)}/30 <em>${fmt(score)} ball</em></b></div><div class="subject-track"><i style="width:${Math.min(100,(Number(correct||0)/30)*100)}%;background:${color}"></i></div></div>`}
function dtmCard(r,index){
  const chronologicalIndex=state.results.findIndex(x=>x.id===r.id);
  const previous=chronologicalIndex>0?state.results[chronologicalIndex-1]:null;
  const change=previous?Number(r.umumiy_ball)-Number(previous.umumiy_ball):null;
  const changeHtml=change==null?'':`<span class="dtm-change ${change>=0?'up':'down'}">${change>=0?'↑':'↓'} ${Math.abs(change).toFixed(1)}</span>`;
  const certText=r.certificate_url?'Sertifikatni ochish':'Sertifikat yaratish';
  return `<article class="dtm-result" data-result-card="${r.id}"><div class="dtm-result-main"><div class="attempt-number">${String(index+1).padStart(2,'0')}</div><div class="dtm-result-copy"><div class="dtm-result-title"><h3>DTM imtihoni</h3>${changeHtml}</div><p>${esc(r.sana)} · ${((Number(r.umumiy_ball||0)/189)*100).toFixed(1)}%</p></div><div class="dtm-result-score"><strong>${fmt(r.umumiy_ball)}</strong><small>/ 189 ball</small></div></div><div class="dtm-result-actions"><button type="button" data-result-toggle="${r.id}" aria-expanded="false">Batafsil <span>${icon('chevronDown')}</span></button><button class="certificate-button" type="button" data-certificate="${r.id}" data-url="${esc(r.certificate_url||'')}">${icon('certificate')} ${certText}</button></div><div class="dtm-result-detail" id="result-detail-${r.id}" hidden>${dtmSubject('Majburiy fanlar',r.majburiy,state.config.MAJBURIY_KOEFF,'#4e7df0')}${dtmSubject('1-asosiy fan',r.asosiy_1,state.config.ASOSIY_1_KOEFF,'#20a16b')}${dtmSubject('2-asosiy fan',r.asosiy_2,state.config.ASOSIY_2_KOEFF,'#f1a126')}</div></article>`;
}
function renderDtm(){
  const list=[...state.results].reverse();
  const last=state.results.at(-1),previous=state.results.at(-2);
  const growth=last&&previous?Number(last.umumiy_ball)-Number(previous.umumiy_ball):null;
  document.getElementById('pageContent').innerHTML=`<section class="dtm-summary"><div><div class="eyebrow">DTM KO‘RSATKICHLARI</div><h2>${esc(state.student.ismlar)}</h2><p>${esc(state.student.yonalish)} · ${esc(state.student.sinf)} · ${esc(state.student.maktab)}</p></div><div class="dtm-summary-score"><small>ENG YUQORI NATIJA</small><strong>${fmt(state.stats.best)}</strong><span>/ 189</span></div></section><div class="metric-grid dtm-metrics"><div class="metric-card"><small>Jami urinish</small><strong>${state.stats.total_tests}</strong></div><div class="metric-card"><small>Oxirgi natija</small><strong>${fmt(state.stats.last)}</strong></div><div class="metric-card"><small>O‘rtacha ball</small><strong>${fmt(state.stats.avg)}</strong></div><div class="metric-card"><small>Oxirgi o‘zgarish</small><strong class="${growth!=null&&growth<0?'negative':'positive'}">${growth==null?'—':`${growth>=0?'+':''}${growth.toFixed(1)}`}</strong></div></div>${list.length?`<section class="panel dtm-analysis"><div class="section-head compact"><div><p>NATIJALAR DINAMIKASI</p><h2>Ballar o‘zgarishi</h2></div><span>MAKSIMAL 189 BALL</span></div>${dtmTrendChart(state.results)}</section>`:''}<div class="section-head"><h2>Barcha urinishlar</h2><p>${list.length} TA NATIJA</p></div><div class="dtm-result-list">${list.length?list.map(dtmCard).join(''):'<div class="panel empty">Hali DTM natijasi yo‘q.</div>'}</div>`;
  bindDtmActions();
}
function bindDtmActions(){
  document.querySelectorAll('[data-result-toggle]').forEach(button=>button.onclick=()=>{const detail=document.getElementById(`result-detail-${button.dataset.resultToggle}`);const willOpen=detail.hidden;detail.hidden=!willOpen;button.setAttribute('aria-expanded',String(willOpen));button.querySelector('span').innerHTML=icon(willOpen?'chevronUp':'chevronDown')});
  document.querySelectorAll('[data-certificate]').forEach(button=>button.onclick=()=>openDtmCertificate(button));
}
async function openDtmCertificate(button){
  if(button.dataset.url){window.open(button.dataset.url,'_blank','noopener');return}
  const certificateWindow=window.open('about:blank','_blank');
  if(certificateWindow)certificateWindow.opener=null;
  const original=button.innerHTML;button.disabled=true;button.textContent='Tayyorlanmoqda...';
  try{
    const response=await fetch('/api/student/dtm/certificate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({result_id:Number(button.dataset.certificate)})});
    const data=await response.json();
    if(response.status===401){location.href='/mock';return}
    if(!response.ok||!data.certificate_url)throw new Error(data.error||'Sertifikat yaratilmadi');
    button.dataset.url=data.certificate_url;button.innerHTML=`${icon('certificate')} Sertifikatni ochish`;
    if(certificateWindow)certificateWindow.location.replace(data.certificate_url);else location.href=data.certificate_url;
  }catch(error){if(certificateWindow)certificateWindow.close();button.innerHTML=original;alert(error.message)}finally{button.disabled=false}
}
async function getMock(){if(state.mock)return state.mock;const r=await fetch('/api/student/mock',{cache:'no-store'});if(!r.ok)throw new Error('Mock natijalari yuklanmadi');state.mock=(await r.json()).mock_results||[];return state.mock}
async function renderMock(){
  const list=await getMock();
  const types=[...new Map(list.map(r=>[r.exam_key,r.exam_label||r.exam_key])).entries()];
  const subjects=[...new Set(list.map(r=>r.subject_name).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  document.getElementById('pageContent').innerHTML=`<section class="mock-summary"><div><div class="eyebrow">MOCK IMTIHONLARI</div><h2>Natijalar markazi</h2><p>IELTS, CEFR, SAT, DTM Mock va Milliy sertifikat natijalaringiz bir joyda.</p></div><div class="mock-summary-mark">${icon('target')}</div></section><div class="metric-grid mock-metrics"><div class="metric-card"><div class="metric-icon">${icon('quiz')}</div><div><small>Jami urinish</small><strong>${list.length}</strong></div></div><div class="metric-card"><div class="metric-icon">${icon('target')}</div><div><small>Imtihon turi</small><strong>${types.length}</strong></div></div><div class="metric-card"><div class="metric-icon">${icon('book')}</div><div><small>Fanlar</small><strong>${subjects.length}</strong></div></div><div class="metric-card"><div class="metric-icon">${icon('calendar')}</div><div><small>Oxirgi sana</small><strong class="date-value">${esc(list[0]?.test_sanasi)}</strong></div></div></div><section class="mock-controls"><div class="filter-row mock-type-filter"><button class="active" data-mock-exam="all">Barchasi</button>${types.map(([k,v])=>`<button data-mock-exam="${esc(k)}">${esc(v)}</button>`).join('')}</div><label>Fan bo‘yicha <select id="mockSubjectFilter"><option value="all">Barcha fanlar</option>${subjects.map(s=>`<option value="${esc(s)}">${esc(s)}</option>`).join('')}</select></label></section><section id="mockAnalysis" class="panel mock-analysis"></section><div class="section-head"><div><p>HISOBOTLAR</p><h2>Mock urinishlar</h2></div><span id="mockCount">${list.length} TA NATIJA</span></div><div id="mockResults" class="mock-result-list"></div>`;
  const filters={exam:'all',subject:'all'};
  const draw=()=>{const rows=list.filter(r=>(filters.exam==='all'||r.exam_key===filters.exam)&&(filters.subject==='all'||r.subject_name===filters.subject));document.getElementById('mockCount').textContent=`${rows.length} TA NATIJA`;document.getElementById('mockAnalysis').innerHTML=mockTrendPanel(rows,filters.exam);document.getElementById('mockResults').innerHTML=rows.length?rows.map(mockCard).join(''):'<div class="panel empty">Tanlangan filtr bo‘yicha natija topilmadi.</div>';bindMockActions()};
  document.querySelectorAll('[data-mock-exam]').forEach(btn=>btn.onclick=()=>{document.querySelectorAll('[data-mock-exam]').forEach(x=>x.classList.remove('active'));btn.classList.add('active');filters.exam=btn.dataset.mockExam;draw()});
  document.getElementById('mockSubjectFilter').onchange=event=>{filters.subject=event.target.value;draw()};
  draw();
}
function mockResultMax(r){if(Number(r.total_max)>0)return Number(r.total_max);const entries=mockSections(r);if(entries.length===1&&Number(entries[0].max)>0)return Number(entries[0].max);return null}
function mockSections(r){const raw=r.sections&&typeof r.sections==='object'?r.sections:{};const config=Array.isArray(r.section_config)?r.section_config:[];const used=new Set();const entries=config.map(item=>{used.add(item.key);const source=raw[item.key];const isObject=source&&typeof source==='object';return {key:item.key,label:(isObject&&source.label)||item.label||item.key,value:isObject?source.value:source,max:(isObject&&source.max)!=null?source.max:item.max_score}});Object.entries(raw).forEach(([key,source])=>{if(used.has(key))return;const isObject=source&&typeof source==='object';entries.push({key,label:(isObject&&source.label)||key,value:isObject?source.value:source,max:isObject?source.max:null})});return entries.filter(x=>x.value!=null&&x.value!=='')}
function mockTrendPanel(rows,exam){
  if(!rows.length)return '<div class="empty">Grafik uchun natija mavjud emas.</div>';
  const chronological=[...rows].reverse(),width=760,height=200,padX=34,padY=27,usableW=width-padX*2,usableH=height-padY*2;
  const points=chronological.map((r,i)=>{const max=mockResultMax(r),percent=max?Math.min(100,(Number(r.umumiy_ball||0)/max)*100):Math.min(100,Number(r.umumiy_ball||0));const x=chronological.length===1?width/2:padX+(i/(chronological.length-1))*usableW;const y=padY+(1-percent/100)*usableH;return {x,y,r,percent}});
  const guides=[0,25,50,75,100].map(value=>{const y=padY+(1-value/100)*usableH;return `<line x1="${padX}" y1="${y}" x2="${width-padX}" y2="${y}"/><text x="2" y="${y+4}">${value}%</text>`}).join('');
  const dots=points.map((p,i)=>`<circle cx="${p.x}" cy="${p.y}" r="5"><title>${esc(p.r.test_sanasi)} — ${fmt(p.r.umumiy_ball)} (${p.percent.toFixed(1)}%)</title></circle>${(i===0||i===points.length-1)?`<text class="chart-date" x="${p.x}" y="${height-4}" text-anchor="${i===0?'start':'end'}">${esc(p.r.test_sanasi)}</text>`:''}`).join('');
  const label=exam==='all'?'Barcha natijalar foizda':'Tanlangan imtihon dinamikasi';
  return `<div class="section-head compact"><div><p>NATIJALAR DINAMIKASI</p><h2>${label}</h2></div><span>NATIJA / MAKSIMUM</span></div><div class="mock-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Mock natijalari dinamikasi"><g class="chart-guides">${guides}</g><polyline points="${points.map(p=>`${p.x},${p.y}`).join(' ')}"/><g class="chart-dots">${dots}</g></svg></div>`;
}
function mockSectionRow(section){const max=Number(section.max)>0?Number(section.max):null;const pct=max?Math.min(100,(Number(section.value||0)/max)*100):0;return `<div class="mock-section-row"><div><span>${esc(section.label)}</span><b>${fmt(section.value)}${max?` / ${fmt(max)}`:''}</b></div>${max?`<div class="subject-track"><i style="width:${pct}%"></i></div>`:''}</div>`}
function mockCard(r){const level=r.level_label?`<span class="mock-level">${esc(r.level_label)}</span>`:'';const max=mockResultMax(r);const sections=mockSections(r);const verifyText=r.verification_url?'Tasdiqlashni ochish':'Tasdiqlash havolasi';return `<article class="mock-result" data-mock-card="${r.id}"><div class="mock-result-head"><div class="mock-result-icon">${icon('target')}</div><div class="mock-result-copy"><div><h3>${esc(r.exam_label||r.exam_key)}</h3>${level}</div><p>${esc(r.subject_name||'Umumiy natija')} · ${esc(r.test_sanasi)}</p></div><div class="mock-score"><strong>${fmt(r.umumiy_ball)}</strong>${max?`<small>/ ${fmt(max)}</small>`:''}</div></div><div class="mock-result-actions"><button type="button" data-mock-toggle="${r.id}">Batafsil <span>${icon('chevronDown')}</span></button><button type="button" data-mock-report="${r.id}">${icon('download')} PDF hisobot</button><button class="mock-verify-button" type="button" data-mock-verify="${r.id}" data-url="${esc(r.verification_url||'')}">${icon('link')} ${verifyText}</button></div><div class="mock-result-detail" id="mock-detail-${r.id}" hidden><div class="mock-section-list">${sections.length?sections.map(mockSectionRow).join(''):'<div class="empty">Bo‘limlar ko‘rsatilmagan.</div>'}</div>${r.notes?`<div class="mock-note"><span>IZOH</span><p>${esc(r.notes)}</p></div>`:''}</div></article>`}
function bindMockActions(){
  document.querySelectorAll('[data-mock-toggle]').forEach(button=>button.onclick=()=>{const detail=document.getElementById(`mock-detail-${button.dataset.mockToggle}`);const open=detail.hidden;detail.hidden=!open;button.querySelector('span').innerHTML=icon(open?'chevronUp':'chevronDown')});
  document.querySelectorAll('[data-mock-report]').forEach(button=>button.onclick=()=>window.open(`/api/student/mock/report/${button.dataset.mockReport}.pdf`,'_blank','noopener'));
  document.querySelectorAll('[data-mock-verify]').forEach(button=>button.onclick=()=>openMockVerification(button));
}
async function openMockVerification(button){
  if(button.dataset.url){window.open(button.dataset.url,'_blank','noopener');return}
  const verificationWindow=window.open('about:blank','_blank');if(verificationWindow)verificationWindow.opener=null;
  const original=button.innerHTML;button.disabled=true;button.textContent='Tayyorlanmoqda...';
  try{const response=await fetch('/api/student/mock/verification',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({result_id:Number(button.dataset.mockVerify)})});const data=await response.json();if(response.status===401){location.href='/mock';return}if(!response.ok||!data.verification_url)throw new Error(data.error||'Havola yaratilmadi');button.dataset.url=data.verification_url;button.innerHTML=`${icon('link')} Tasdiqlashni ochish`;if(verificationWindow)verificationWindow.location.replace(data.verification_url);else location.href=data.verification_url}catch(error){if(verificationWindow)verificationWindow.close();button.innerHTML=original;alert(error.message)}finally{button.disabled=false}
}
function renderRanking(){
  const hasRank=state.stats.sinf_rank&&state.stats.sinf_rank!=='—';
  const rankValue=hasRank?state.stats.sinf_rank:'—';
  const rankCopy=hasRank?`${esc(state.student.sinf)} sinfida DTM natijasi mavjud ${esc(state.stats.sinf_rank_total)} nafar o‘quvchi orasida`:'Sinfdagi o‘rinni hisoblash uchun DTM natijasi kerak.';
  document.getElementById('pageContent').innerHTML=`<section class="class-rank-hero"><div class="class-rank-copy"><div class="eyebrow">SINF REYTINGI</div><h2>${esc(state.student.ismlar)}</h2><p>${rankCopy}</p><div class="rank-method">Oxirgi DTM natijasi asosida · Teng ball — bir xil o‘rin</div></div><div class="class-rank-position"><small>SIZNING O‘RNINGIZ</small><strong>${hasRank?'#':''}${esc(rankValue)}</strong>${hasRank?`<span>${fmt(state.stats.last)} ball</span>`:''}</div></section><section class="panel rank-info rank-method-panel"><h2>Hisoblash tartibi</h2><div class="profile-lines"><div class="profile-line"><span>Reyting hududi</span><b>${esc(state.student.maktab)}, ${esc(state.student.sinf)}</b></div><div class="profile-line"><span>Natija turi</span><b>Oxirgi DTM</b></div><div class="profile-line"><span>Reytingdagilar</span><b>${esc(state.stats.sinf_rank_total)} nafar</b></div><div class="profile-line"><span>Sizning ballingiz</span><b>${hasRank?`${fmt(state.stats.last)} ball`:'Natija yo‘q'}</b></div></div></section>`;
}
function renderClassroom(){
  const classmates=state.classmates||[];
  document.getElementById('pageContent').innerHTML=`<section class="classroom-hero"><div><div class="eyebrow">MENING SINFIM</div><h2>${esc(state.student.sinf)}</h2><p>${esc(state.student.maktab)}</p></div><div class="classroom-count"><strong>${classmates.length}</strong><span>o‘quvchi</span></div></section><section class="panel classroom-panel"><div class="section-head compact"><div><p>SINFDOSHLAR</p><h2>O‘quvchilar ro‘yxati</h2></div><span>ALIFBO TARTIBIDA</span></div><div class="classroom-list">${classmates.length?classmates.map((student,index)=>{const isCurrent=student.ismlar===state.student.ismlar;return `<div class="classroom-student ${isCurrent?'current':''}"><div class="classroom-index">${String(index+1).padStart(2,'0')}</div><div class="classroom-avatar">${initials(student.ismlar)}</div><strong>${esc(student.ismlar)}</strong>${isCurrent?'<span>Siz</span>':''}</div>`}).join(''):'<div class="empty">Sinfdoshlar topilmadi.</div>'}</div></section>`;
}
async function renderLearning(){
  const [scheduleResponse,materialsResponse]=await Promise.all([fetch('/api/schedule'),fetch('/api/materials')]);
  const schedule=(await scheduleResponse.json()).schedule||[];const materials=(await materialsResponse.json()).materials||[];
  const materialRows=materials.slice(0,8).map(item=>`<a class="material-row" href="${safeUrl(item.link)}" target="_blank" rel="noopener"><div class="material-icon">${icon(item.turi==='video'?'play':'file')}</div><div><strong>${esc(item.nomi)}</strong><span>${esc(item.fanni_nomi||'Umumiy')} · ${esc(item.turi||'material')}</span></div><i>${icon('arrow')}</i></a>`).join('');
  const scheduleRows=schedule.slice(0,6).map(item=>`<div class="schedule-row"><div class="schedule-date">${icon('calendar')}<strong>${esc(item.sana)}</strong></div><div><b>${esc(item.test_nomi)}</b><span>${esc(item.vaqt||'Vaqt belgilanmagan')} · ${esc(item.sinf||'Barchaga')}</span></div></div>`).join('');
  document.getElementById('pageContent').innerHTML=`<section class="learning-hero"><div><div class="eyebrow">O‘QISH MARKAZI</div><h2>Bilimingizni mustahkamlang</h2><p>Testlar, o‘quv materiallari va yaqin imtihonlar bir sahifada.</p></div><a href="/mock/home">${icon('play')} Testni boshlash</a></section><div class="learning-shortcuts"><a href="/mock/home"><span>${icon('target')}</span><div><b>Mock testlar</b><small>Faol testni boshlang</small></div>${icon('arrow')}</a><div><span>${icon('file')}</span><div><b>${materials.length} ta material</b><small>O‘quv resurslari</small></div></div><div><span>${icon('calendar')}</span><div><b>${schedule.length} ta reja</b><small>Yaqin testlar</small></div></div><div><span>${icon('quiz')}</span><div><b>Mini-testlar</b><small>Tezkor mashqlar</small></div></div></div><div class="learning-content-grid"><section class="panel learning-panel"><div class="section-head compact"><div><p>O‘QUV RESURSLARI</p><h2>So‘nggi materiallar</h2></div><span>${materials.length} TA</span></div><div class="material-list">${materialRows||'<div class="empty">Hozircha material mavjud emas.</div>'}</div></section><section class="panel learning-panel"><div class="section-head compact"><div><p>TAQVIM</p><h2>Yaqin testlar</h2></div><span>${schedule.length} TA</span></div><div class="schedule-list">${scheduleRows||'<div class="empty">Yaqin testlar rejalashtirilmagan.</div>'}</div></section></div>`;
}
function renderServices(){
  const linked=state.student.telegram?.linked;
  document.getElementById('pageContent').innerHTML=`<section class="services-hero"><div><div class="eyebrow">KABINET XIZMATLARI</div><h2>Profil va sozlamalar</h2><p>Shaxsiy ma’lumotlar, QR-kod, xabarlar va yordam xizmatlarini boshqaring.</p></div><div class="services-status"><i></i><span>${linked?'Telegram ulangan':'Telegram ulanmagan'}</span></div></section><div class="service-grid services-grid"><button class="service-button" data-service="profile"><span>${icon('user')}</span><b>Shaxsiy profil</b><small>Kabinet va Telegram ma’lumotlari</small></button><button class="service-button" data-service="qr"><span>${icon('qr')}</span><b>Mening QR-kodim</b><small>Ko‘rish va qurilmaga yuklash</small></button><button class="service-button" data-service="notifications"><span>${icon('bell')}</span><b>Bildirishnomalar</b><small>Xabar turlarini boshqarish</small></button><button class="service-button" data-service="contact"><span>${icon('message')}</span><b>Admin bilan bog‘lanish</b><small>Yordam uchun murojaat yuborish</small></button><button class="service-button danger-service" data-service="session"><span>${icon('logout')}</span><b>Kabinetdan chiqish</b><small>Joriy sessiyani yakunlash</small></button><div id="serviceDetail" class="service-detail services-detail"></div></div>`;
  document.querySelectorAll('[data-service]').forEach(btn=>btn.onclick=()=>{document.querySelectorAll('[data-service]').forEach(x=>x.classList.remove('active'));btn.classList.add('active');openService(btn.dataset.service)});
  const first=document.querySelector('[data-service="profile"]');first.classList.add('active');openService('profile');
}
async function openService(service){
  const box=document.getElementById('serviceDetail');
  if(service==='qr'){box.innerHTML=`<div class="service-detail-head"><div><div class="eyebrow">SHAXSIY IDENTIFIKATOR</div><h3>Mening QR-kodim</h3><p>Davomat yoki shaxsni tasdiqlashda ushbu kodni ko‘rsating.</p></div></div><div class="qr-service"><div class="qr-frame"><img src="/api/student/qr?ts=${Date.now()}" alt="${esc(state.student.ismlar)} QR-kodi"></div><div class="qr-copy"><small>SHAXSIY KOD</small><strong>${esc(state.student.kod)}</strong><p>QR-kodni begona shaxslarga yubormang. Unda shaxsiy kodingiz mavjud.</p><div class="service-actions"><a class="service-primary" href="/api/student/qr?download=1">${icon('download')} QR-kodni yuklash</a><button type="button" id="copyStudentCode">${icon('certificate')} Koddan nusxa olish</button></div><span id="copyCodeStatus" class="service-message"></span></div></div>`;document.getElementById('copyStudentCode').onclick=()=>copyStudentCode()}
  if(service==='profile')renderProfile(box);
  if(service==='notifications')await renderNotifications(box);
  if(service==='contact')renderContact(box);
  if(service==='session'){box.innerHTML=`<div class="service-detail-head"><div><div class="eyebrow">XAVFSIZLIK</div><h3>Kabinetdan chiqish</h3><p>Joriy brauzerdagi tasdiqlangan sessiya yakunlanadi.</p></div></div><div class="session-card"><div><strong>${esc(state.student.ismlar)}</strong><span>${esc(state.student.kod)} · ${esc(state.student.sinf)}</span></div><button type="button" id="serviceLogout">${icon('logout')} Kabinetdan chiqish</button></div>`;document.getElementById('serviceLogout').onclick=logout}
}
function renderProfile(box){const telegram=state.student.telegram||{};const username=telegram.username?`@${String(telegram.username).replace(/^@/,'')}`:'Ko‘rsatilmagan';box.innerHTML=`<div class="service-detail-head"><div><div class="eyebrow">SHAXSIY MA’LUMOTLAR</div><h3>${esc(state.student.ismlar)}</h3><p>Ma’lumotlarda xato bo‘lsa, admin bilan bog‘laning.</p></div><span class="linked-badge ${telegram.linked?'linked':'unlinked'}">${telegram.linked?'● Telegram ulangan':'○ Ulanmagan'}</span></div><div class="profile-service-grid"><div class="profile-lines"><div class="profile-line"><span>Shaxsiy kod</span><b>${esc(state.student.kod)}</b></div><div class="profile-line"><span>Maktab</span><b>${esc(state.student.maktab)}</b></div><div class="profile-line"><span>Sinf</span><b>${esc(state.student.sinf)}</b></div><div class="profile-line"><span>Yo‘nalish</span><b>${esc(state.student.yonalish)}</b></div></div><div class="profile-lines telegram-profile"><div class="profile-line"><span>Telegram</span><b>${esc(username)}</b></div><div class="profile-line"><span>Telefon</span><b>${esc(telegram.phone||'Ko‘rsatilmagan')}</b></div><div class="profile-line"><span>Bot</span><b><a href="https://t.me/${esc(state.config.BOT_USERNAME)}" target="_blank" rel="noopener">@${esc(state.config.BOT_USERNAME)}</a></b></div></div></div><div class="service-actions"><button type="button" id="profileCopyCode">Shaxsiy koddan nusxa olish</button></div><span id="copyCodeStatus" class="service-message"></span>`;document.getElementById('profileCopyCode').onclick=()=>copyStudentCode()}
async function copyStudentCode(){const status=document.getElementById('copyCodeStatus');try{await navigator.clipboard.writeText(state.student.kod);status.textContent='Kod nusxalandi.';status.className='service-message success'}catch(error){status.textContent=`Kod: ${state.student.kod}`;status.className='service-message'}setTimeout(()=>{if(status)status.textContent=''},2500)}
async function renderNotifications(box){
  box.innerHTML='<div class="service-loading">Sozlamalar yuklanmoqda...</div>';const response=await fetch('/api/student/notifications');const data=await response.json();if(!response.ok){box.innerHTML=`<div class="empty">${esc(data.error||'Sozlamalar yuklanmadi.')}</div>`;return}const labels={notify_results:['DTM natijalari','Yangi DTM natijasi kiritilganda'],notify_mock_results:['Mock natijalari','Yangi mock natijasi kiritilganda'],notify_admin_messages:['Admin xabarlari','Muhim e’lon va shaxsiy xabarlar'],notify_reminders:['Eslatmalar','Test va tadbir eslatmalari']};box.innerHTML=`<div class="service-detail-head"><div><div class="eyebrow">XABAR SOZLAMALARI</div><h3>Bildirishnomalar</h3><p>Qaysi xabarlar Telegram orqali kelishini tanlang.</p></div></div><div class="notification-list">${Object.entries(labels).map(([key,value])=>`<label class="notification-row"><span><b>${value[0]}</b><small>${value[1]}</small></span><input data-notification="${key}" type="checkbox" role="switch" ${data.settings?.[key]!==false?'checked':''}></label>`).join('')}</div><p id="notificationStatus" class="service-message"></p>`;document.querySelectorAll('[data-notification]').forEach(input=>input.onchange=()=>saveNotification(input))
}
async function saveNotification(input){const status=document.getElementById('notificationStatus'),previous=!input.checked;input.disabled=true;status.textContent='Saqlanmoqda...';status.className='service-message';try{const response=await fetch('/api/student/notifications',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:input.dataset.notification,enabled:input.checked})});const data=await response.json();if(!response.ok)throw new Error(data.error||'Sozlama saqlanmadi');status.textContent='Sozlama saqlandi.';status.className='service-message success'}catch(error){input.checked=previous;status.textContent=error.message;status.className='service-message error'}finally{input.disabled=false}}
function renderContact(box){box.innerHTML=`<div class="service-detail-head"><div><div class="eyebrow">YORDAM MARKAZI</div><h3>Admin bilan bog‘lanish</h3><p>Murojaatingiz Telegram orqali administratorlarga yuboriladi.</p></div></div><div class="contact-form"><label for="contactText">Murojaat matni</label><textarea id="contactText" maxlength="2000" placeholder="Savol yoki muammoingizni batafsil yozing..."></textarea><div class="contact-meta"><span id="contactCounter">0 / 2000</span><button id="contactSend" type="button">${icon('message')} Murojaatni yuborish</button></div><p id="contactStatus" class="service-message"></p></div>`;const area=document.getElementById('contactText'),counter=document.getElementById('contactCounter');area.oninput=()=>counter.textContent=`${area.value.length} / 2000`;document.getElementById('contactSend').onclick=async()=>{const text=area.value.trim(),status=document.getElementById('contactStatus'),button=document.getElementById('contactSend'),original=button.innerHTML;if(!text){status.textContent='Murojaat matnini yozing.';status.className='service-message error';return}button.disabled=true;button.textContent='Yuborilmoqda...';try{const response=await fetch('/api/student/contact-admin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});const data=await response.json();if(!response.ok)throw new Error(data.error||'Xatolik yuz berdi.');status.textContent='Murojaatingiz adminga yuborildi.';status.className='service-message success';area.value='';counter.textContent='0 / 2000'}catch(error){status.textContent=error.message;status.className='service-message error'}finally{button.disabled=false;button.innerHTML=original}}}
