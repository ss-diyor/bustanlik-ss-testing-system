/* ─────────────────────────────────────────
   Bustanlik SS Testing System — Web App JS
   ───────────────────────────────────────── */

const tg = window.Telegram?.WebApp;
let progressChart = null;
let subjectChart  = null;
let lastResults   = null;

// Mock bo'limi o'zgaruvchilari
let mockChartInstance = null;
let currentMockFilter = 'all';
let lastConfig    = null;

// ─── Init ───────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  if (tg) {
    tg.ready();
    tg.expand();
    tg.onEvent("themeChanged", applyTelegramTheme);
  }
  applyTelegramTheme();
  loadStudentData();
});

// ─── Theme ──────────────────────────────
function applyTelegramTheme() {
  const p = tg?.themeParams;
  if (p) {
    const r = document.documentElement.style;
    if (p.bg_color)              r.setProperty("--tg-theme-bg-color",           p.bg_color);
    if (p.text_color)            r.setProperty("--tg-theme-text-color",         p.text_color);
    if (p.hint_color)            r.setProperty("--tg-theme-hint-color",         p.hint_color);
    if (p.link_color)            r.setProperty("--tg-theme-link-color",         p.link_color);
    if (p.button_color)          r.setProperty("--tg-theme-button-color",       p.button_color);
    if (p.button_text_color)     r.setProperty("--tg-theme-button-text-color",  p.button_text_color);
    if (p.secondary_bg_color)    r.setProperty("--tg-theme-secondary-bg-color", p.secondary_bg_color);
    document.body.style.background = p.bg_color || "";
  }
  syncColorScheme();
  // Re-render charts so axis/tooltip colors match the new theme
  if (lastResults) {
    renderProgressChart(lastResults);
    if (lastResults.length > 0) renderSubjectChart(lastResults[lastResults.length - 1], lastConfig);
  }
  // Mock chart ham yangilansin
  if (mockLoaded) {
    const filtered = currentMockFilter === 'all'
      ? allMockResults
      : allMockResults.filter(r => r.exam_key === currentMockFilter);
    renderMockChart(filtered, currentMockFilter);
  }
}

// Toggle the `light` class so the CSS light palette kicks in.
function syncColorScheme() {
  let isLight;
  if (tg?.colorScheme) {
    isLight = tg.colorScheme === "light";
  } else if (tg?.themeParams?.bg_color) {
    isLight = isLightColor(tg.themeParams.bg_color);
  } else {
    isLight = window.matchMedia?.("(prefers-color-scheme: light)").matches ?? false;
  }
  document.body.classList.toggle("light", isLight);
}

// Perceived luminance check for a #rrggbb / #rgb color.
function isLightColor(hex) {
  const m = String(hex).trim().replace("#", "");
  const full = m.length === 3 ? m.split("").map(c => c + c).join("") : m;
  if (full.length < 6) return false;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) > 150;
}

// Read a CSS custom property from the live theme.
function cssVar(name, fallback) {
  const v = getComputedStyle(document.body).getPropertyValue(name).trim();
  return v || fallback;
}

// ─── Fetch data ──────────────────────────
async function loadStudentData() {
  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) {
      headers["X-Telegram-Init-Data"] = tg.initData;
    }

    const res = await fetch("/api/student", { headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showError(err.error || "Ma'lumot topilmadi");
      return;
    }

    const data = await res.json();
    renderPage(data);
  } catch (e) {
    showError("Server bilan bog'lanib bo'lmadi. Qayta urinib ko'ring.");
  }
}

// ─── Render ──────────────────────────────
function renderPage(data) {
  const { student, stats, results, classmates, config } = data;
  lastResults = results;
  lastConfig  = config;
  
  // Student info
  const initials = (student.ismlar || "?")
    .split(" ")
    .map(w => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  document.getElementById("avatar-initials").textContent   = initials;
  document.getElementById("student-name").textContent      = student.ismlar || "—";
  document.getElementById("student-meta").textContent      =
    `${student.maktab || "—"} | ${student.sinf || "—"} · ${student.yonalish || "—"} · Kod: ${student.kod || "—"}`;

  // Stats
  document.getElementById("stat-last").textContent  = stats.last  ?? "—";
  document.getElementById("stat-best").textContent  = stats.best  ?? "—";
  document.getElementById("stat-avg").textContent   = stats.avg   ?? "—";
  document.getElementById("stat-rank").textContent  = stats.sinf_rank != null
    ? `${stats.sinf_rank}-o'rin` : "—";

  // Trend badge
  const badge = document.getElementById("trend-badge");
  if (results.length >= 2) {
    const t = stats.trend;
    if (t > 0) {
      badge.textContent = `📈 Oldingi testga nisbatan: +${t} ball o'sish`;
      badge.className = "trend-badge up";
    } else if (t < 0) {
      badge.textContent = `📉 Oldingi testga nisbatan: ${t} ball pasayish`;
      badge.className = "trend-badge down";
    } else {
      badge.textContent = "➡️ Oldingi testga nisbatan: o'zgarish yo'q";
      badge.className = "trend-badge neutral";
    }
  } else {
    badge.classList.add("hidden");
  }

  // Charts
  renderProgressChart(results);
  if (results.length > 0) renderSubjectChart(results[results.length - 1], config);

  // History table
  renderHistoryTable(results);

  // Classmates table
  if (classmates) {
    renderClassmates(classmates);
  }

  // Show app
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
}

// ─── Tab Switching ────────────────────────
function switchTab(tabId) {
  // Update buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  const activeBtn = document.querySelector(`.tab-btn[onclick="switchTab('${tabId}')"]`);
  if (activeBtn) activeBtn.classList.add('active');

  // Update content
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.remove('active-tab');
    content.classList.add('hidden');
  });
  const activeTab = document.getElementById(`tab-${tabId}`);
  if (activeTab) {
    activeTab.classList.remove('hidden');
    activeTab.classList.add('active-tab');
  }

  // Load tab-specific data
  if (tabId === 'schedule') loadSchedule();
  if (tabId === 'materials') loadMaterials();
  if (tabId === 'mock') loadMockResults();
}

function servicePanel() {
  const panel = document.getElementById('service-panel');
  panel.classList.remove('hidden');
  return panel;
}

function showStudentQr() {
  const panel = servicePanel();
  panel.innerHTML = `<h3>🆔 Mening QR-kodim</h3><p>Davomatdan o'tishda ushbu QR-kodni ko'rsating.</p><img src="/api/student/qr?ts=${Date.now()}" alt="Shaxsiy QR-kod">`;
}

async function showNotifications() {
  const panel = servicePanel();
  panel.innerHTML = '<h3>🔔 Bildirishnomalar</h3><p>Yuklanmoqda...</p>';
  try {
    const data = await (await fetch('/api/student/notifications')).json();
    const labels = {
      notify_results: 'DTM natijalari', notify_mock_results: 'Mock natijalari',
      notify_admin_messages: 'Admin xabarlari', notify_reminders: 'Eslatmalar'
    };
    panel.innerHTML = `<h3>🔔 Bildirishnomalar</h3>${Object.entries(labels).map(([key, label]) => `<div class="notification-row"><label for="${key}">${label}</label><input id="${key}" type="checkbox" ${data.settings?.[key] !== false ? 'checked' : ''}></div>`).join('')}`;
    Object.keys(labels).forEach(key => document.getElementById(key).addEventListener('change', async event => {
      await fetch('/api/student/notifications', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({key, enabled:event.target.checked})});
    }));
  } catch (_) { panel.innerHTML = '<h3>🔔 Bildirishnomalar</h3><p class="empty-msg">Sozlamalarni yuklab bo‘lmadi.</p>'; }
}

function showContactAdmin() {
  const panel = servicePanel();
  panel.innerHTML = `<h3>✍️ Admin bilan bog'lanish</h3><textarea id="admin-message" maxlength="2000" placeholder="Murojaatingizni yozing..."></textarea><button id="send-admin-message">Yuborish</button><p id="contact-status"></p>`;
  document.getElementById('send-admin-message').onclick = async () => {
    const button = document.getElementById('send-admin-message');
    const status = document.getElementById('contact-status');
    const message = document.getElementById('admin-message').value.trim();
    if (!message) { status.textContent = 'Murojaat matnini yozing.'; return; }
    button.disabled = true;
    try {
      const res = await fetch('/api/student/contact-admin', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message})});
      const data = await res.json();
      status.textContent = res.ok ? '✅ Murojaatingiz adminga yuborildi.' : (data.error || 'Xatolik yuz berdi.');
      if (res.ok) document.getElementById('admin-message').value = '';
    } catch (_) { status.textContent = 'Server bilan bog‘lanib bo‘lmadi.'; }
    button.disabled = false;
  };
}

// ─── Load Schedule ────────────────────────
async function loadSchedule() {
  const wrap = document.getElementById("schedule-list");
  wrap.innerHTML = '<div class="spinner-small"></div>';
  
  try {
    const res = await fetch("/api/schedule");
    const data = await res.json();
    
    if (!data.schedule || !data.schedule.length) {
      wrap.innerHTML = '<p class="empty-msg">Yaqin orada testlar rejalashtirilmagan.</p>';
      return;
    }
    
    wrap.innerHTML = data.schedule.map(s => `
      <div class="card-item">
        <div class="card-content">
          <h3>${s.test_nomi}</h3>
          <p>${s.sinf || 'Barchaga'} · ${s.vaqt || 'Vaqt belgilanmagan'}</p>
        </div>
        <div class="card-tag">${s.sana}</div>
      </div>
    `).join('');
  } catch (e) {
    wrap.innerHTML = '<p class="empty-msg">Xatolik yuz berdi.</p>';
  }
}

// ─── Load Materials ───────────────────────
let allMaterials = [];

async function loadMaterials() {
  const wrap = document.getElementById("materials-list");
  const filterWrap = document.getElementById("materials-filter");
  wrap.innerHTML = '<div class="spinner-small"></div>';
  
  try {
    const res = await fetch("/api/materials");
    const data = await res.json();
    
    if (!data.materials || !data.materials.length) {
      wrap.innerHTML = '<p class="empty-msg">Materiallar hali yuklanmagan.</p>';
      filterWrap.innerHTML = '';
      return;
    }

    allMaterials = data.materials;
    
    // Create filters
    const subjects = [...new Set(allMaterials.map(m => m.fanni_nomi || 'Umumiy'))];
    let filterHtml = '<button class="filter-btn active" onclick="filterMaterials(\'all\')">Barchasi</button>';
    subjects.forEach(s => {
      filterHtml += `<button class="filter-btn" onclick="filterMaterials('${s}')">${s}</button>`;
    });
    filterWrap.innerHTML = filterHtml;

    renderMaterials(allMaterials);
  } catch (e) {
    wrap.innerHTML = '<p class="empty-msg">Xatolik yuz berdi.</p>';
  }
}

function filterMaterials(subject) {
  // Update active button
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.textContent === subject || (subject === 'all' && btn.textContent === 'Barchasi'));
  });

  const filtered = subject === 'all' 
    ? allMaterials 
    : allMaterials.filter(m => (m.fanni_nomi || 'Umumiy') === subject);
  
  renderMaterials(filtered);
}

function renderMaterials(list) {
  const wrap = document.getElementById("materials-list");
  if (!list.length) {
    wrap.innerHTML = '<p class="empty-msg">Ushbu fan bo\'yicha materiallar yo\'q.</p>';
    return;
  }

  wrap.innerHTML = list.map(m => `
    <div class="card-item">
      <div class="card-content">
        <h3>${m.nomi}</h3>
        <p>${m.fanni_nomi || 'Umumiy'} · ${m.turi.toUpperCase()}</p>
      </div>
      <a href="${m.link}" target="_blank" class="card-btn">Ochish</a>
    </div>
  `).join('');
}

// ─── Progress Line Chart ─────────────────
function renderProgressChart(results) {
  const labels = results.map(r => r.sana);
  const balls  = results.map(r => r.umumiy_ball);

  const ctx = document.getElementById("progressChart").getContext("2d");
  if (progressChart) progressChart.destroy();

  const tick = cssVar("--chart-tick", "rgba(255,255,255,0.45)");
  const grid = cssVar("--chart-grid", "rgba(255,255,255,0.06)");
  const isLight = document.body.classList.contains("light");
  const surface = cssVar("--tg-theme-secondary-bg-color", "#16213e");
  const textCol = cssVar("--tg-theme-text-color", "#e8e8f0");
  const pointBg = isLight ? (cssVar("--tg-theme-bg-color", "#ffffff") || "#ffffff") : "#fff";

  // Gradient fill
  const grad = ctx.createLinearGradient(0, 0, 0, 200);
  grad.addColorStop(0, "rgba(114,137,218,0.45)");
  grad.addColorStop(1, "rgba(114,137,218,0)");

  progressChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Umumiy ball",
          data: balls,
          borderColor: "#7289da",
          backgroundColor: grad,
          borderWidth: 2.5,
          tension: 0.35,
          fill: true,
          pointRadius: 5,
          pointBackgroundColor: pointBg,
          pointBorderColor: "#7289da",
          pointBorderWidth: 2,
          pointHoverRadius: 7,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "nearest", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: surface,
          titleColor: textCol,
          bodyColor: "#7289da",
          borderColor: cssVar("--card-border", "rgba(255,255,255,0.1)"),
          borderWidth: 1,
          callbacks: {
            label: ctx => `  ${ctx.parsed.y} ball`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: tick, maxTicksLimit: 6, font: { size: 10 } },
          grid:  { color: grid },
        },
        y: {
          ticks: { color: tick, font: { size: 10 } },
          grid:  { color: grid },
          beginAtZero: false,
        },
      },
    },
  });
}

// ─── Subject Doughnut / Bar Chart ────────
function renderSubjectChart(last, config) {
  const MAJBURIY_KOEFF  = config?.MAJBURIY_KOEFF  || 1.1;
  const ASOSIY_1_KOEFF  = config?.ASOSIY_1_KOEFF  || 3.1;
  const ASOSIY_2_KOEFF  = config?.ASOSIY_2_KOEFF  || 2.1;

  const mBall  = (last.majburiy  * MAJBURIY_KOEFF).toFixed(1);
  const a1Ball = (last.asosiy_1  * ASOSIY_1_KOEFF).toFixed(1);
  const a2Ball = (last.asosiy_2  * ASOSIY_2_KOEFF).toFixed(1);

  const ctx = document.getElementById("subjectChart").getContext("2d");
  if (subjectChart) subjectChart.destroy();

  const tick = cssVar("--chart-tick", "rgba(255,255,255,0.45)");
  const grid = cssVar("--chart-grid", "rgba(255,255,255,0.06)");
  const surface = cssVar("--tg-theme-secondary-bg-color", "#16213e");
  const textCol = cssVar("--tg-theme-text-color", "#e8e8f0");

  subjectChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Majburiy (×1.1)", "1-asosiy (×3.1)", "2-asosiy (×2.1)"],
      datasets: [
        {
          data: [mBall, a1Ball, a2Ball],
          backgroundColor: ["#5865f2", "#43b581", "#faa61a"],
          borderRadius: 8,
          borderSkipped: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: surface,
          titleColor: textCol,
          bodyColor: "#7289da",
          callbacks: { label: ctx => `  ${ctx.parsed.y} ball` },
        },
      },
      scales: {
        x: {
          ticks: { color: tick, font: { size: 10 } },
          grid:  { display: false },
        },
        y: {
          ticks: { color: tick, font: { size: 10 } },
          grid:  { color: grid },
          beginAtZero: true,
        },
      },
    },
  });
}

// ─── History table ────────────────────────
function renderHistoryTable(results) {
  const wrap = document.getElementById("history-table");
  if (!results.length) {
    wrap.innerHTML = `<p style="text-align:center;padding:20px;color:var(--tg-theme-hint-color)">Hozircha natijalar yo'q</p>`;
    return;
  }

  // Show newest first
  const rows = [...results].reverse();
  let html = `<div class="hist-row header">
    <span>Sana</span><span style="text-align:right">Ball</span><span style="text-align:right">Farq</span>
  </div>`;

  rows.forEach((r, i) => {
    const prev = rows[i + 1];
    let deltaHtml = '<span class="hist-delta delta-neutral">—</span>';
    if (prev) {
      const d = +(r.umumiy_ball - prev.umumiy_ball).toFixed(1);
      if (d > 0) deltaHtml = `<span class="hist-delta delta-up">+${d}</span>`;
      else if (d < 0) deltaHtml = `<span class="hist-delta delta-down">${d}</span>`;
      else deltaHtml = `<span class="hist-delta delta-neutral">0</span>`;
    }

    // Color ball based on score level
    const b = r.umumiy_ball;
    const ballColor = b >= 140 ? "#43b581" : b >= 100 ? "#faa61a" : "#f04747";

    html += `<div class="hist-row">
      <span class="hist-sana">${r.sana}</span>
      <span class="hist-ball" style="color:${ballColor}">${b}</span>
      ${deltaHtml}
    </div>`;
  });

  wrap.innerHTML = html;
}

// ─── Classmates List ──────────────────────
function renderClassmates(classmates) {
  const wrap = document.getElementById("classmates-list");
  if (!classmates || !classmates.length) {
    wrap.innerHTML = `<p style="text-align:center;padding:20px;color:var(--tg-theme-hint-color)">Sinfdoshlar topilmadi</p>`;
    return;
  }

  let html = '';
  
  classmates.forEach((c, i) => {
    html += `
      <div class="classmate-row" style="grid-template-columns: 24px 1fr;">
        <span class="classmate-rank" style="color: var(--tg-theme-hint-color); font-weight: normal;">•</span>
        <span class="classmate-name" style="padding-right:0;">${c.ismlar}</span>
      </div>
    `;
  });

  wrap.innerHTML = html;
}

// ─── Error ────────────────────────────────
function showError(msg) {
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("error-msg").textContent = msg;
  document.getElementById("error-screen").classList.remove("hidden");
}

// ─── Mock Natijalar ───────────────────────
let allMockResults = [];
let mockLoaded = false;

// Milliy sertifikat foiz jadvali
const MILLIY_FOIZ = {
  75: 100, 74: 100, 73: 100, 72: 100, 71: 100, 70: 100,
  69: 100, 68: 100, 67: 100, 66: 100, 65: 100,
  64: 98.46, 63: 96.92, 62: 95.38, 61: 93.85, 60: 92.31,
  59: 90.77, 58: 89.23, 57: 87.69, 56: 86.15, 55: 84.62,
  54: 83.08, 53: 81.54, 52: 80.00, 51: 78.46, 50: 76.92,
  49: 75.38, 48: 73.85, 47: 72.31, 46: 70.77,
};

function milliyDaraja(ball) {
  if (ball >= 70) return 'A+';
  if (ball >= 65) return 'A';
  if (ball >= 60) return 'B+';
  if (ball >= 55) return 'B';
  if (ball >= 50) return 'C+';
  if (ball >= 46) return 'C';
  return null;
}

function milliyFoiz(ball) {
  const key = Math.floor(ball);
  return MILLIY_FOIZ[key] ?? null;
}

// DD.MM.YYYY → Date (grafik uchun tartib)
function parseMockDate(str) {
  if (!str) return new Date(0);
  const p = str.split('.');
  return p.length === 3 ? new Date(+p[2], +p[1] - 1, +p[0]) : new Date(str);
}

// Ball formatlash (IELTS: 1 decimal, katta sonlar: butun)
function fmtBall(val, examKey) {
  if (val == null) return '—';
  if (examKey === 'IELTS' || (val < 10 && val % 1 !== 0)) return val.toFixed(1);
  return Number.isInteger(val) ? String(val) : val.toFixed(1);
}

// ─── Ma'lumot yuklash ──────────────────────
async function loadMockResults() {
  if (mockLoaded) return;
  const wrap = document.getElementById('mock-list');
  const filterWrap = document.getElementById('mock-filter');
  wrap.innerHTML = '<div class="spinner-small"></div>';

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (tg?.initData) headers['X-Telegram-Init-Data'] = tg.initData;

    const res = await fetch('/api/student/mock', { headers });
    const data = await res.json();

    if (!data.mock_results || !data.mock_results.length) {
      wrap.innerHTML = '<p class="empty-msg">Hali mock imtihon natijalari yo\'q.</p>';
      filterWrap.innerHTML = '';
      document.getElementById('mock-stats-row').style.display = 'none';
      document.getElementById('mock-chart-section').style.display = 'none';
      return;
    }

    allMockResults = data.mock_results;
    mockLoaded = true;

    // Filter tugmalari
    const seen = new Map();
    allMockResults.forEach(r => {
      if (!seen.has(r.exam_key)) seen.set(r.exam_key, r.exam_label || r.exam_key);
    });
    let filterHtml = '<button class="filter-btn active" onclick="filterMock(\'all\')">Barchasi</button>';
    seen.forEach((label, key) => {
      filterHtml += `<button class="filter-btn" onclick="filterMock('${key}')">${label}</button>`;
    });
    filterWrap.innerHTML = filterHtml;

    renderMockStats(allMockResults, 'all');
    renderMockChart(allMockResults, 'all');
    renderMockResults(allMockResults);
  } catch (e) {
    wrap.innerHTML = '<p class="empty-msg">Xatolik yuz berdi. Qayta urinib ko\'ring.</p>';
  }
}

// ─── Filter ────────────────────────────────
function filterMock(examKey) {
  currentMockFilter = examKey;
  document.querySelectorAll('#mock-filter .filter-btn').forEach(btn => {
    const isAll  = examKey === 'all' && btn.textContent.trim() === 'Barchasi';
    const isMatch = btn.getAttribute('onclick') === `filterMock('${examKey}')`;
    btn.classList.toggle('active', isAll || isMatch);
  });
  const filtered = examKey === 'all'
    ? allMockResults
    : allMockResults.filter(r => r.exam_key === examKey);
  renderMockStats(filtered, examKey);
  renderMockChart(filtered, examKey);
  renderMockResults(filtered);
}

// ─── Statistika qatori ─────────────────────
function renderMockStats(list, examKey) {
  const row = document.getElementById('mock-stats-row');
  if (!list.length) { row.style.display = 'none'; return; }
  row.style.display = 'grid';

  if (examKey === 'all') {
    const uniqueTypes = new Set(list.map(r => r.exam_key)).size;
    const lastSana = list[0]?.test_sanasi || '—';
    row.style.gridTemplateColumns = 'repeat(4, 1fr)';
    row.innerHTML = `
      <div class="stat-card">
        <span class="stat-value">${list.length}</span>
        <span class="stat-label">Jami urinish</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">${uniqueTypes}</span>
        <span class="stat-label">Imtihon turi</span>
      </div>
      <div class="stat-card" style="grid-column:span 2;">
        <span class="stat-value" style="font-size:0.9rem;">${lastSana}</span>
        <span class="stat-label">Oxirgi sana</span>
      </div>`;
  } else {
    const withBall = list.filter(r => r.umumiy_ball != null);
    const best = withBall.length ? Math.max(...withBall.map(r => r.umumiy_ball)) : null;
    const avg  = withBall.length
      ? withBall.reduce((s, r) => s + r.umumiy_ball, 0) / withBall.length : null;
    const last = list[0]?.umumiy_ball ?? null;
    row.style.gridTemplateColumns = 'repeat(4, 1fr)';
    row.innerHTML = `
      <div class="stat-card">
        <span class="stat-value">${list.length}</span>
        <span class="stat-label">Urinishlar</span>
      </div>
      <div class="stat-card">
        <span class="stat-value mock-best-stat">${fmtBall(best, examKey)}</span>
        <span class="stat-label">Eng yuqori</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">${avg != null ? fmtBall(Math.round(avg * 10) / 10, examKey) : '—'}</span>
        <span class="stat-label">O'rtacha</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">${fmtBall(last, examKey)}</span>
        <span class="stat-label">Oxirgi</span>
      </div>`;
  }
}

// ─── Progress grafigi ──────────────────────
function renderMockChart(list, examKey) {
  const section  = document.getElementById('mock-chart-section');
  const chartWrap = document.getElementById('mock-chart-wrap');
  const titleEl  = document.getElementById('mock-chart-title');

  if (!list.length) { section.style.display = 'none'; return; }
  section.style.display = 'block';

  const tick    = cssVar('--chart-tick', 'rgba(255,255,255,0.45)');
  const grid    = cssVar('--chart-grid', 'rgba(255,255,255,0.06)');
  const surface = cssVar('--tg-theme-secondary-bg-color', '#16213e');
  const textCol = cssVar('--tg-theme-text-color', '#e8e8f0');
  const isLight = document.body.classList.contains('light');
  const pointBg = isLight ? '#ffffff' : '#1a1a2e';

  const ctx = document.getElementById('mockProgressChart').getContext('2d');
  if (mockChartInstance) { mockChartInstance.destroy(); mockChartInstance = null; }

  // ── "Barchasi" rejimi: gorizontal bar (har tur soni) ──
  if (examKey === 'all') {
    titleEl.textContent = '📊 Imtihon turlari bo\'yicha urinishlar';
    const countMap = new Map();
    const labelMap = new Map();
    list.forEach(r => {
      countMap.set(r.exam_key, (countMap.get(r.exam_key) || 0) + 1);
      if (!labelMap.has(r.exam_key)) labelMap.set(r.exam_key, r.exam_label || r.exam_key);
    });
    const barLabels = [...labelMap.values()];
    const barData   = [...countMap.values()];
    chartWrap.style.height = Math.max(130, barLabels.length * 46 + 56) + 'px';

    mockChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: barLabels,
        datasets: [{
          data: barData,
          backgroundColor: 'rgba(114,137,218,0.55)',
          borderColor: '#7289da',
          borderWidth: 1.5,
          borderRadius: 6,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: surface, titleColor: textCol, bodyColor: '#7289da',
            callbacks: { label: c => `  ${c.parsed.x} ta urinish` },
          },
        },
        scales: {
          x: {
            ticks: { color: tick, font: { size: 10 }, stepSize: 1 },
            grid: { color: grid },
            beginAtZero: true,
          },
          y: {
            ticks: { color: tick, font: { size: 11 } },
            grid: { color: 'transparent' },
          },
        },
      },
    });
    return;
  }

  // ── Bitta tur: chiziqli grafik (vaqt bo'yicha) ──
  titleEl.textContent = '📈 Natijalar Dinamikasi';
  chartWrap.style.height = '220px';

  const withBall = list.filter(r => r.umumiy_ball != null);
  if (!withBall.length) { section.style.display = 'none'; return; }

  // Xronologik tartib (eskidan yangi)
  const sorted = [...withBall].sort((a, b) => parseMockDate(a.test_sanasi) - parseMockDate(b.test_sanasi));
  const labels = sorted.map(r => r.test_sanasi || '—');
  const balls  = sorted.map(r => r.umumiy_ball);

  // O'rtacha gorizontal chiziq
  const avgVal = Math.round(balls.reduce((s, v) => s + v, 0) / balls.length * 10) / 10;
  const avgLine = balls.map(() => avgVal);

  // Gradient to'ldirish
  const grad = ctx.createLinearGradient(0, 0, 0, 200);
  grad.addColorStop(0, 'rgba(114,137,218,0.42)');
  grad.addColorStop(1, 'rgba(114,137,218,0)');

  // Eng yuqori ball nuqtasini ajratib ko'rsatish
  const maxBall   = Math.max(...balls);
  const maxIdx    = balls.lastIndexOf(maxBall);
  const pointRadii = balls.map((_, i) => i === maxIdx ? 8 : 5);
  const pointBorderColors = balls.map((_, i) => i === maxIdx ? '#faa61a' : '#7289da');
  const pointBorderWidths = balls.map((_, i) => i === maxIdx ? 3 : 2);

  mockChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Ball',
          data: balls,
          borderColor: '#7289da',
          backgroundColor: grad,
          borderWidth: 2.5,
          tension: 0.35,
          fill: true,
          pointRadius: pointRadii,
          pointBackgroundColor: pointBg,
          pointBorderColor: pointBorderColors,
          pointBorderWidth: pointBorderWidths,
          pointHoverRadius: 8,
        },
        {
          label: "O'rtacha",
          data: avgLine,
          borderColor: 'rgba(114,137,218,0.38)',
          borderWidth: 1.5,
          borderDash: [5, 4],
          pointRadius: 0,
          fill: false,
          tension: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'nearest', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: surface,
          titleColor: textCol,
          bodyColor: '#7289da',
          borderColor: cssVar('--card-border', 'rgba(255,255,255,0.1)'),
          borderWidth: 1,
          filter: item => item.datasetIndex === 0,
          callbacks: {
            label: c => {
              const suffix = c.dataIndex === maxIdx ? '  🏆 Eng yaxshi' : '';
              return `  ${c.parsed.y} ball${suffix}`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: tick, maxTicksLimit: 6, font: { size: 10 } },
          grid:  { color: grid },
        },
        y: {
          ticks: { color: tick, font: { size: 10 } },
          grid:  { color: grid },
          beginAtZero: false,
        },
      },
    },
  });
}

// ─── Natijalar ro'yxati ────────────────────
function renderMockResults(list) {
  const wrap = document.getElementById('mock-list');
  if (!list.length) {
    wrap.innerHTML = '<p class="empty-msg">Bu tur bo\'yicha natijalar yo\'q.</p>';
    return;
  }

  // Eng yaxshi natija id-sini aniqlash
  const withBall = list.filter(r => r.umumiy_ball != null);
  const maxBall  = withBall.length ? Math.max(...withBall.map(r => r.umumiy_ball)) : null;
  const bestId   = withBall.find(r => r.umumiy_ball === maxBall)?.id ?? null;

  wrap.innerHTML = list.map(r => {
    const sections = r.sections || {};
    const isBest   = r.id === bestId && bestId != null;

    // MILLIY_SERT: umumiy_ball null bo'lsa o'rtacha hisobla
    let computedBall = r.umumiy_ball;
    if (r.exam_key === 'MILLIY_SERT' && computedBall == null) {
      const vals = Object.values(sections)
        .map(v => typeof v === 'object' ? (v.value ?? null) : v)
        .filter(v => v != null);
      if (vals.length) computedBall = Math.round(vals.reduce((a, b) => a + b, 0) / vals.length * 10) / 10;
    }

    const sectionRows = Object.entries(sections).map(([key, val]) => {
      const score = typeof val === 'object' ? (val.value ?? val.score ?? val.ball ?? '—') : val;
      const label = typeof val === 'object' ? (val.label || key) : key;
      return `<div class="mock-brow"><span>${label}</span><b>${score}</b></div>`;
    }).join('');

    const ball        = computedBall != null ? computedBall : '—';
    const levelBadge  = r.level_label  ? `<span class="mock-level-badge">${r.level_label}</span>` : '';
    const noteHtml    = r.notes        ? `<p class="mock-notes">📝 ${r.notes}</p>` : '';
    const subjectHtml = r.subject_name ? `<span class="mock-subject">${r.subject_name}</span>` : '';
    const bestBadge   = isBest         ? '<span class="mock-best-badge">🏆 Eng yaxshi</span>' : '';

    // MILLIY_SERT uchun daraja + foiz bloki
    let scoreHtml;
    if (r.exam_key === 'MILLIY_SERT' && computedBall != null) {
      const daraja = milliyDaraja(computedBall);
      const foiz   = milliyFoiz(computedBall);
      const darajaHtml = daraja
        ? `<span class="milliy-daraja milliy-daraja--${daraja.replace('+', 'plus')}">${daraja}</span>` : '';
      const foizHtml = foiz != null ? `<span class="milliy-foiz">${foiz}%</span>` : '';
      scoreHtml = `
        <div class="milliy-score-row">
          <span class="mock-score milliy-inline">${computedBall}</span>
          ${darajaHtml}${foizHtml}
        </div>`;
    } else {
      scoreHtml = `<div class="mock-score">${ball}</div>`;
    }

    return `
      <div class="mock-card${isBest ? ' mock-card-best' : ''}">
        <div class="mock-card-header">
          <div class="mock-header-left">
            <span class="mock-exam-label">${r.exam_label || r.exam_key}</span>
            ${levelBadge}${subjectHtml}${bestBadge}
          </div>
          <span class="mock-date">${r.test_sanasi || '—'}</span>
        </div>
        ${scoreHtml}
        ${sectionRows ? `<div class="mock-breakdown">${sectionRows}</div>` : ''}
        ${noteHtml}
      </div>`;
  }).join('');
}
