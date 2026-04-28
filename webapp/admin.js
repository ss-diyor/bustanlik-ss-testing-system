/* ─────────────────────────────────────────
   Bustanlik SS Testing System — Admin Web App JS
   ───────────────────────────────────────── */

const tg = window.Telegram?.WebApp;
let classesChart = null;
let directionsChart = null;

// ─── Init ───────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  if (tg) {
    tg.ready();
    tg.expand();
    applyTelegramTheme();
    tg.onEvent("themeChanged", applyTelegramTheme);
  }
  loadAdminData();
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
async function loadAdminData() {
  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) {
      headers["X-Telegram-Init-Data"] = tg.initData;
    }

    const res = await fetch("/api/admin_stats", { headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showError(err.error || "Sizda admin huquqi yo'q yoki xatolik yuz berdi");
      return;
    }

    const data = await res.json();
    renderPage(data);
  } catch (e) {
    showError("Server bilan bog'lanib bo'lmadi. Qayta urinib ko'ring.");
  }
}

// ─── Render ──────────────────────────────
function renderPage({ kpi, class_stats, direction_stats, top_students }) {
  // Stats
  document.getElementById("stat-students").textContent = kpi.total_students ?? "—";
  document.getElementById("stat-tests").textContent    = kpi.total_tests ?? "—";
  document.getElementById("stat-avg").textContent      = kpi.school_avg ? kpi.school_avg.toFixed(1) : "—";

  // Charts
  if (class_stats && class_stats.length > 0) {
    renderClassesChart(class_stats);
  } else {
    document.getElementById("classesChart").parentElement.style.display = 'none';
  }

  if (direction_stats && direction_stats.length > 0) {
    renderDirectionsChart(direction_stats);
  } else {
    document.getElementById("directionsChart").parentElement.style.display = 'none';
  }

  // Top Students Table
  renderTopStudentsTable(top_students);

  // Show app
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
}

// ─── Bar Chart: Classes ─────────────────
function renderClassesChart(class_stats) {
  const labels = class_stats.map(s => s.sinf);
  const data = class_stats.map(s => s.avg_score);

  const ctx = document.getElementById("classesChart").getContext("2d");
  if (classesChart) classesChart.destroy();

  classesChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "O'rtacha ball",
          data,
          backgroundColor: "#43b581",
          borderRadius: 4,
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
        x: { ticks: { color: "rgba(255,255,255,0.5)", font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: "rgba(255,255,255,0.45)", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.06)" }, beginAtZero: true },
      },
    },
  });
}

// ─── Bar Chart: Directions ─────────────────
function renderDirectionsChart(direction_stats) {
  const labels = direction_stats.map(s => s.yonalish || "Umumiy");
  const data = direction_stats.map(s => s.avg_score);

  const ctx = document.getElementById("directionsChart").getContext("2d");
  if (directionsChart) directionsChart.destroy();

  directionsChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "O'rtacha ball",
          data,
          backgroundColor: "#faa61a",
          borderRadius: 4,
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
        x: { ticks: { color: "rgba(255,255,255,0.5)", font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: "rgba(255,255,255,0.45)", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.06)" }, beginAtZero: true },
      },
    },
  });
}

// ─── Top Students table ────────────────────────
function renderTopStudentsTable(students) {
  const wrap = document.getElementById("top-students-list");
  if (!students || !students.length) {
    wrap.innerHTML = `<p style="text-align:center;padding:20px;color:var(--tg-theme-hint-color)">Hozircha natijalar yo'q</p>`;
    return;
  }

  let html = '';
  
  students.forEach((s, i) => {
    const rank = i + 1;
    let rankClass = '';
    if (rank === 1) rankClass = 'top-1';
    else if (rank === 2) rankClass = 'top-2';
    else if (rank === 3) rankClass = 'top-3';

    let scoreHtml = '<span class="classmate-score" style="color:var(--tg-theme-hint-color)">Yo\'q</span>';
    if (s.umumiy_ball !== null) {
      const b = parseFloat(s.umumiy_ball).toFixed(1);
      const ballColor = b >= 140 ? "#43b581" : b >= 100 ? "#faa61a" : "#f04747";
      scoreHtml = `<span class="classmate-score" style="color:${ballColor}">${b}</span>`;
    }

    html += `
      <div class="classmate-row" style="grid-template-columns: 28px 1fr 60px;">
        <span class="classmate-rank ${rankClass}">${rank}</span>
        <div style="display:flex; flex-direction:column; padding-right:10px;">
          <span class="classmate-name">${s.ismlar}</span>
          <span style="font-size: 0.7rem; color: var(--tg-theme-hint-color);">${s.sinf} | ${s.yonalish || 'Umumiy'}</span>
        </div>
        ${scoreHtml}
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
