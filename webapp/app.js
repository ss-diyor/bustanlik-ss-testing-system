/* ─────────────────────────────────────────
   Bustanlik SS Testing System — Web App JS
   ───────────────────────────────────────── */

const tg = window.Telegram?.WebApp;
let progressChart = null;
let subjectChart  = null;

// ─── Init ───────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  if (tg) {
    tg.ready();
    tg.expand();
    applyTelegramTheme();
    tg.onEvent("themeChanged", applyTelegramTheme);
  }
  loadStudentData();
});

// ─── Theme ──────────────────────────────
function applyTelegramTheme() {
  if (!tg?.themeParams) return;
  const p = tg.themeParams;
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
    `${student.sinf || "—"} · ${student.yonalish || "—"} · Kod: ${student.kod || "—"}`;

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
          pointBackgroundColor: "#fff",
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
          backgroundColor: "rgba(22,33,62,0.95)",
          titleColor: "#e8e8f0",
          bodyColor: "#7289da",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
          callbacks: {
            label: ctx => `  ${ctx.parsed.y} ball`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "rgba(255,255,255,0.45)", maxTicksLimit: 6, font: { size: 10 } },
          grid:  { color: "rgba(255,255,255,0.06)" },
        },
        y: {
          ticks: { color: "rgba(255,255,255,0.45)", font: { size: 10 } },
          grid:  { color: "rgba(255,255,255,0.06)" },
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
          backgroundColor: "rgba(22,33,62,0.95)",
          titleColor: "#e8e8f0",
          bodyColor: "#aaaacc",
          callbacks: { label: ctx => `  ${ctx.parsed.y} ball` },
        },
      },
      scales: {
        x: {
          ticks: { color: "rgba(255,255,255,0.5)", font: { size: 10 } },
          grid:  { display: false },
        },
        y: {
          ticks: { color: "rgba(255,255,255,0.45)", font: { size: 10 } },
          grid:  { color: "rgba(255,255,255,0.06)" },
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
