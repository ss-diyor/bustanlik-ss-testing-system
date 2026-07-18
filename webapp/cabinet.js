const state = { student:null, stats:null, results:[], classmates:[], config:null, mock:null };
const page = location.pathname.split('/').filter(Boolean)[1] || 'home';
const titles = {
  home:['O‘QUVCHI KABINETI','Bosh sahifa'], dtm:['NATIJALAR','DTM natijalar'],
  mock:['NATIJALAR','Mock natijalar'], ranking:['STATISTIKA','Sinf reytingi'],
  classroom:['SINF','Mening sinfim'],
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
  if(target==='classroom') renderClassroom();
  if(target==='learning') await renderLearning();
  if(target==='services') renderServices();
}
function hero(){return `<section class="hero"><div><div class="kicker">XUSH KELIBSIZ</div><h2>${esc(state.student.ismlar)}</h2><p>${esc(state.student.maktab)} · ${esc(state.student.sinf)} · ${esc(state.student.yonalish)} · Kod: ${esc(state.student.kod)}</p></div><div class="hero-avatar">${initials(state.student.ismlar)}</div></section>`}
function metrics(){const rank=state.stats.sinf_rank&&state.stats.sinf_rank!=='—'?`${esc(state.stats.sinf_rank)}-o‘rin`:'—';return `<div class="metric-grid"><div class="metric-card"><small>Oxirgi ball</small><strong>${fmt(state.stats.last)}</strong></div><div class="metric-card"><small>Eng yuqori</small><strong>${fmt(state.stats.best)}</strong></div><div class="metric-card"><small>O‘rtacha</small><strong>${fmt(state.stats.avg)}</strong></div><div class="metric-card"><small>Sinf o‘rni</small><strong>${rank}</strong></div></div>`}
function renderHome(){
  const latest=[...state.results].reverse().slice(0,3);
  document.getElementById('pageContent').innerHTML=hero()+metrics()+`<div class="section-head"><h2>Asosiy bo‘limlar</h2><p>TEZKOR KIRISH</p></div><div class="action-grid"><a class="action-card" href="/cabinet/dtm"><div class="icon">▥</div><h3>DTM natijalar</h3><p>Natijalar dinamikasi va barcha urinishlar.</p></a><a class="action-card" href="/cabinet/mock"><div class="icon">◎</div><h3>Mock natijalar</h3><p>IELTS, Milliy sertifikat va boshqa mocklar.</p></a><a class="action-card" href="/mock/home"><div class="icon">＋</div><h3>Test ishlash</h3><p>Faol mock imtihonlarni boshlang yoki davom ettiring.</p></a></div><div class="section-head"><h2>Oxirgi DTM natijalar</h2><p>${state.results.length} TA NATIJA</p></div><div class="result-list">${latest.length?latest.map(dtmCompactCard).join(''):'<div class="panel empty">Hali DTM natijasi mavjud emas.</div>'}</div>`;
}
function dtmCompactCard(r){return `<article class="result-card"><div><h3>DTM imtihoni</h3><p>${esc(r.sana)} · Majburiy: ${fmt(r.majburiy)} · 1-asosiy: ${fmt(r.asosiy_1)} · 2-asosiy: ${fmt(r.asosiy_2)}</p></div><div class="score">${fmt(r.umumiy_ball)}</div></article>`}
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
  return `<article class="dtm-result" data-result-card="${r.id}"><div class="dtm-result-main"><div class="attempt-number">${String(index+1).padStart(2,'0')}</div><div class="dtm-result-copy"><div class="dtm-result-title"><h3>DTM imtihoni</h3>${changeHtml}</div><p>${esc(r.sana)} · ${((Number(r.umumiy_ball||0)/189)*100).toFixed(1)}%</p></div><div class="dtm-result-score"><strong>${fmt(r.umumiy_ball)}</strong><small>/ 189 ball</small></div></div><div class="dtm-result-actions"><button type="button" data-result-toggle="${r.id}" aria-expanded="false">Batafsil <span>⌄</span></button><button class="certificate-button" type="button" data-certificate="${r.id}" data-url="${esc(r.certificate_url||'')}">▤ ${certText}</button></div><div class="dtm-result-detail" id="result-detail-${r.id}" hidden>${dtmSubject('Majburiy fanlar',r.majburiy,state.config.MAJBURIY_KOEFF,'#4e7df0')}${dtmSubject('1-asosiy fan',r.asosiy_1,state.config.ASOSIY_1_KOEFF,'#20a16b')}${dtmSubject('2-asosiy fan',r.asosiy_2,state.config.ASOSIY_2_KOEFF,'#f1a126')}</div></article>`;
}
function renderDtm(){
  const list=[...state.results].reverse();
  const last=state.results.at(-1),previous=state.results.at(-2);
  const growth=last&&previous?Number(last.umumiy_ball)-Number(previous.umumiy_ball):null;
  document.getElementById('pageContent').innerHTML=`<section class="dtm-summary"><div><div class="eyebrow">DTM KO‘RSATKICHLARI</div><h2>${esc(state.student.ismlar)}</h2><p>${esc(state.student.yonalish)} · ${esc(state.student.sinf)} · ${esc(state.student.maktab)}</p></div><div class="dtm-summary-score"><small>ENG YUQORI NATIJA</small><strong>${fmt(state.stats.best)}</strong><span>/ 189</span></div></section><div class="metric-grid dtm-metrics"><div class="metric-card"><small>Jami urinish</small><strong>${state.stats.total_tests}</strong></div><div class="metric-card"><small>Oxirgi natija</small><strong>${fmt(state.stats.last)}</strong></div><div class="metric-card"><small>O‘rtacha ball</small><strong>${fmt(state.stats.avg)}</strong></div><div class="metric-card"><small>Oxirgi o‘zgarish</small><strong class="${growth!=null&&growth<0?'negative':'positive'}">${growth==null?'—':`${growth>=0?'+':''}${growth.toFixed(1)}`}</strong></div></div>${list.length?`<section class="panel dtm-analysis"><div class="section-head compact"><div><p>NATIJALAR DINAMIKASI</p><h2>Ballar o‘zgarishi</h2></div><span>MAKSIMAL 189 BALL</span></div>${dtmTrendChart(state.results)}</section>`:''}<div class="section-head"><h2>Barcha urinishlar</h2><p>${list.length} TA NATIJA</p></div><div class="dtm-result-list">${list.length?list.map(dtmCard).join(''):'<div class="panel empty">Hali DTM natijasi yo‘q.</div>'}</div>`;
  bindDtmActions();
}
function bindDtmActions(){
  document.querySelectorAll('[data-result-toggle]').forEach(button=>button.onclick=()=>{const detail=document.getElementById(`result-detail-${button.dataset.resultToggle}`);const willOpen=detail.hidden;detail.hidden=!willOpen;button.setAttribute('aria-expanded',String(willOpen));button.querySelector('span').textContent=willOpen?'⌃':'⌄'});
  document.querySelectorAll('[data-certificate]').forEach(button=>button.onclick=()=>openDtmCertificate(button));
}
async function openDtmCertificate(button){
  if(button.dataset.url){window.open(button.dataset.url,'_blank','noopener');return}
  const certificateWindow=window.open('about:blank','_blank');
  if(certificateWindow)certificateWindow.opener=null;
  const original=button.textContent;button.disabled=true;button.textContent='Tayyorlanmoqda...';
  try{
    const response=await fetch('/api/student/dtm/certificate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({result_id:Number(button.dataset.certificate)})});
    const data=await response.json();
    if(response.status===401){location.href='/mock';return}
    if(!response.ok||!data.certificate_url)throw new Error(data.error||'Sertifikat yaratilmadi');
    button.dataset.url=data.certificate_url;button.textContent='▤ Sertifikatni ochish';
    if(certificateWindow)certificateWindow.location.replace(data.certificate_url);else location.href=data.certificate_url;
  }catch(error){if(certificateWindow)certificateWindow.close();button.textContent=original;alert(error.message)}finally{button.disabled=false}
}
async function getMock(){if(state.mock)return state.mock;const r=await fetch('/api/student/mock',{cache:'no-store'});if(!r.ok)throw new Error('Mock natijalari yuklanmadi');state.mock=(await r.json()).mock_results||[];return state.mock}
async function renderMock(){
  const list=await getMock();
  const types=[...new Map(list.map(r=>[r.exam_key,r.exam_label||r.exam_key])).entries()];
  const subjects=[...new Set(list.map(r=>r.subject_name).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  document.getElementById('pageContent').innerHTML=`<section class="mock-summary"><div><div class="eyebrow">MOCK IMTIHONLARI</div><h2>Natijalar markazi</h2><p>IELTS, CEFR, SAT, DTM Mock va Milliy sertifikat natijalaringiz bir joyda.</p></div><div class="mock-summary-mark">◎</div></section><div class="metric-grid mock-metrics"><div class="metric-card"><small>Jami urinish</small><strong>${list.length}</strong></div><div class="metric-card"><small>Imtihon turi</small><strong>${types.length}</strong></div><div class="metric-card"><small>Fanlar</small><strong>${subjects.length}</strong></div><div class="metric-card"><small>Oxirgi sana</small><strong class="date-value">${esc(list[0]?.test_sanasi)}</strong></div></div><section class="mock-controls"><div class="filter-row mock-type-filter"><button class="active" data-mock-exam="all">Barchasi</button>${types.map(([k,v])=>`<button data-mock-exam="${esc(k)}">${esc(v)}</button>`).join('')}</div><label>Fan bo‘yicha <select id="mockSubjectFilter"><option value="all">Barcha fanlar</option>${subjects.map(s=>`<option value="${esc(s)}">${esc(s)}</option>`).join('')}</select></label></section><section id="mockAnalysis" class="panel mock-analysis"></section><div class="section-head"><h2>Mock urinishlar</h2><p id="mockCount">${list.length} TA NATIJA</p></div><div id="mockResults" class="mock-result-list"></div>`;
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
function mockCard(r){const level=r.level_label?`<span class="mock-level">${esc(r.level_label)}</span>`:'';const max=mockResultMax(r);const sections=mockSections(r);const verifyText=r.verification_url?'Tasdiqlashni ochish':'Tasdiqlash havolasi';return `<article class="mock-result" data-mock-card="${r.id}"><div class="mock-result-head"><div class="mock-result-icon">◎</div><div class="mock-result-copy"><div><h3>${esc(r.exam_label||r.exam_key)}</h3>${level}</div><p>${esc(r.subject_name||'Umumiy natija')} · ${esc(r.test_sanasi)}</p></div><div class="mock-score"><strong>${fmt(r.umumiy_ball)}</strong>${max?`<small>/ ${fmt(max)}</small>`:''}</div></div><div class="mock-result-actions"><button type="button" data-mock-toggle="${r.id}">Batafsil <span>⌄</span></button><button type="button" data-mock-report="${r.id}">↓ PDF hisobot</button><button class="mock-verify-button" type="button" data-mock-verify="${r.id}" data-url="${esc(r.verification_url||'')}">⌁ ${verifyText}</button></div><div class="mock-result-detail" id="mock-detail-${r.id}" hidden><div class="mock-section-list">${sections.length?sections.map(mockSectionRow).join(''):'<div class="empty">Bo‘limlar ko‘rsatilmagan.</div>'}</div>${r.notes?`<div class="mock-note"><span>IZOH</span><p>${esc(r.notes)}</p></div>`:''}</div></article>`}
function bindMockActions(){
  document.querySelectorAll('[data-mock-toggle]').forEach(button=>button.onclick=()=>{const detail=document.getElementById(`mock-detail-${button.dataset.mockToggle}`);const open=detail.hidden;detail.hidden=!open;button.querySelector('span').textContent=open?'⌃':'⌄'});
  document.querySelectorAll('[data-mock-report]').forEach(button=>button.onclick=()=>window.open(`/api/student/mock/report/${button.dataset.mockReport}.pdf`,'_blank','noopener'));
  document.querySelectorAll('[data-mock-verify]').forEach(button=>button.onclick=()=>openMockVerification(button));
}
async function openMockVerification(button){
  if(button.dataset.url){window.open(button.dataset.url,'_blank','noopener');return}
  const verificationWindow=window.open('about:blank','_blank');if(verificationWindow)verificationWindow.opener=null;
  const original=button.textContent;button.disabled=true;button.textContent='Tayyorlanmoqda...';
  try{const response=await fetch('/api/student/mock/verification',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({result_id:Number(button.dataset.mockVerify)})});const data=await response.json();if(response.status===401){location.href='/mock';return}if(!response.ok||!data.verification_url)throw new Error(data.error||'Havola yaratilmadi');button.dataset.url=data.verification_url;button.textContent='⌁ Tasdiqlashni ochish';if(verificationWindow)verificationWindow.location.replace(data.verification_url);else location.href=data.verification_url}catch(error){if(verificationWindow)verificationWindow.close();button.textContent=original;alert(error.message)}finally{button.disabled=false}
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
