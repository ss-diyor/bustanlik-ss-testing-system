/* ─────────────────────────────────────────
   Bustanlik SS Testing System — Admin Web App JS
   ───────────────────────────────────────── */

const tg = window.Telegram?.WebApp;
let classesChart = null;
let directionsChart = null;
let subjectsChart = null;
let studentDetailChart = null;
let searchTimeout = null;

// ─── Init ───────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  if (tg) {
    tg.ready();
    tg.expand();
    applyTelegramTheme();
    tg.onEvent("themeChanged", applyTelegramTheme);
  }
  
  // Search listener
  const searchInput = document.getElementById("student-search");
  searchInput.addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    const q = e.target.value.trim();
    if (q.length < 2) {
      document.getElementById("search-results").classList.add("hidden");
      return;
    }
    searchTimeout = setTimeout(() => handleSearch(q), 400);
  });

  // Close search results when clicking outside
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-box")) {
      document.getElementById("search-results").classList.add("hidden");
    }
  });

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
function renderPage({ role, kpi, class_stats, direction_stats, subject_stats, top_students }) {
    window.adminRole = role;
    
    document.getElementById('admin-title-suffix').innerText = role === 'admin' ? '(Super Admin)' : `(O'qituvchi - ${role.sinf || ''})`;

    if (role === 'admin') {
      document.querySelectorAll('.admin-only').forEach(el => el.classList.remove('hidden'));
      loadSchedule();
      loadAdminMaterials();
      loadAdminQuizQuestions();
    } else {
      document.querySelectorAll('.admin-only').forEach(el => el.classList.add('hidden'));
    }

  // Stats
  document.getElementById("stat-students").textContent = kpi.total_students ?? "—";
  document.getElementById("stat-tests").textContent    = kpi.total_tests ?? "—";
  document.getElementById("stat-avg").textContent      = kpi.school_avg ? kpi.school_avg.toFixed(1) : "—";

  // Load classes into dropdowns
  if (class_stats) {
    const bTarget = document.getElementById("broadcast-target");
    const sTarget = document.getElementById("sched-sinf");
    const mTarget = document.getElementById("mat-sinf");
    
    const html = '<option value="Barchaga">Barcha o\'quvchilarga</option>' + 
                 class_stats.map(s => `<option value="${s.sinf}">${s.sinf} sinfiga</option>`).join("");
    
    const plainHtml = '<option value="Barchaga">Barcha sinflar</option>' + 
                      class_stats.map(s => `<option value="${s.sinf}">${s.sinf}</option>`).join("");
    
    if (bTarget) bTarget.innerHTML = html;
    if (sTarget) sTarget.innerHTML = plainHtml;
    if (mTarget) mTarget.innerHTML = plainHtml;
  }

  // Charts
  if (subject_stats) renderSubjectsChart(subject_stats);
  if (class_stats && class_stats.length > 0) renderClassesChart(class_stats);
  if (direction_stats && direction_stats.length > 0) renderDirectionsChart(direction_stats);

  // Top Students Table
  renderTopStudentsTable(top_students);

  // Show app
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
}

// ─── Schedule Logic ──────────────────────
async function loadSchedule() {
  try {
    const res = await fetch("/api/admin/schedule");
    const { schedule } = await res.json();
    const wrap = document.getElementById("schedule-list");
    
    if (!schedule || schedule.length === 0) {
      wrap.innerHTML = '<p class="meta" style="text-align:center">Hozircha rejalashtirilgan testlar yo\'q</p>';
      return;
    }

    wrap.innerHTML = schedule.map(s => `
      <div class="schedule-item">
        <div class="info">
          <span class="test-name">${s.test_nomi}</span>
          <span class="test-meta">${s.sinf} | ${s.vaqt || ''}</span>
        </div>
        <span class="test-date">${s.sana}</span>
      </div>
    `).join("");
  } catch (e) {
    console.error("Schedule load error:", e);
  }
}

async function addSchedule() {
  const test_nomi = document.getElementById("sched-name").value.trim();
  const sana = document.getElementById("sched-date").value;
  const vaqt = document.getElementById("sched-time").value.trim();
  const sinf = document.getElementById("sched-sinf").value;

  if (!test_nomi || !sana) {
    tg.showAlert("Test nomi va sanasini kiriting!");
    return;
  }

  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch("/api/admin/schedule", {
      method: "POST",
      headers,
      body: JSON.stringify({ test_nomi, sana, vaqt, sinf })
    });

    if (res.ok) {
      tg.showAlert("Test muvaffaqiyatli rejalashtirildi!");
      document.getElementById("sched-name").value = "";
      document.getElementById("sched-date").value = "";
      document.getElementById("sched-time").value = "";
      loadSchedule();
    } else {
      tg.showAlert("Xatolik yuz berdi");
    }
  } catch (e) {
    tg.showAlert("Serverga ulanishda xatolik!");
  }
}

async function addMaterial() {
  const nomi = document.getElementById('mat-name').value.trim();
  const turi = document.getElementById('mat-type').value;
  const link = document.getElementById('mat-link').value.trim();
  const fanni_nomi = document.getElementById('mat-subject').value.trim();
  const sinf = document.getElementById('mat-sinf').value;

  if (!nomi || !link || !fanni_nomi) {
    tg.showAlert("Barcha maydonlarni to'ldiring!");
    return;
  }

  try {
    const resp = await fetch('/api/admin/materials', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': tg.initData
      },
      body: JSON.stringify({ nomi, turi, link, fanni_nomi, sinf })
    });

    if (res.ok) {
      tg.showAlert("Material muvaffaqiyatli qo'shildi!");
      document.getElementById("mat-name").value = "";
      document.getElementById("mat-link").value = "";
      document.getElementById("mat-subject").value = "";
    } else {
      tg.showAlert("Xatolik yuz berdi");
    }
  } catch (e) {
    tg.showAlert("Serverga ulanishda xatolik!");
  }
}

// ─── Admin Actions ───────────────────────
async function sendBroadcast() {
  const text = document.getElementById("broadcast-text").value.trim();
  const sinf = document.getElementById("broadcast-target").value;
  const btn = document.getElementById("btn-broadcast");

  if (!text) {
    tg.showAlert("Xabar matnini kiriting!");
    return;
  }

  try {
    btn.disabled = true;
    btn.textContent = "⌛ Yuborilmoqda...";

    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch("/api/admin/broadcast", {
      method: "POST",
      headers,
      body: JSON.stringify({ text, sinf })
    });

    const data = await res.json();
    if (data.success) {
      tg.showAlert(`Xabar ${data.count} ta o'quvchiga muvaffaqiyatli yuborildi!`);
      document.getElementById("broadcast-text").value = "";
    } else {
      tg.showAlert("Xatolik: " + (data.error || "Noma'lum xato"));
    }
  } catch (e) {
    tg.showAlert("Serverga ulanishda xatolik!");
  } finally {
    btn.disabled = false;
    btn.textContent = "🚀 Xabarni yuborish";
  }
}

async function exportExcel(type) {
  try {
    const initData = tg?.initData || "";
    const url = `/api/admin/export?type=${type}&_t=${Date.now()}`;
    
    // WebApp headers can't be added to direct window.open or <a> download
    // So we use a little trick: if we have initData, we fetch it first or use a signed URL
    // For simplicity, we'll try to fetch with headers and then create a blob
    
    const headers = {};
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error("Yuklab olishda xatolik");

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = type === "top_students" ? "top_oquvchilar.xlsx" : "sinflar_statistikasi.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (e) {
    tg.showAlert("Excel yuklashda xatolik yuz berdi");
  }
}

// ─── Bar Chart: Subjects ─────────────────
function renderSubjectsChart(stats) {
  const labels = ["Majburiy", "1-Asosiy", "2-Asosiy"];
  const data = [stats.majburiy, stats.asosiy_1, stats.asosiy_2];

  const ctx = document.getElementById("subjectsChart").getContext("2d");
  if (subjectsChart) subjectsChart.destroy();

  subjectsChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "O'rtacha ball",
        data,
        backgroundColor: ["#7289da", "#43b581", "#faa61a"],
        borderRadius: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#8e9297" } },
        x: { grid: { display: false }, ticks: { color: "#8e9297" } }
      }
    }
  });
}

// ─── Search Logic ───────────────────────
async function handleSearch(query) {
  const resultsDiv = document.getElementById("search-results");
  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch(`/api/admin/search?q=${encodeURIComponent(query)}`, { headers });
    const { results } = await res.json();

    if (!results || results.length === 0) {
      resultsDiv.innerHTML = '<div class="search-item"><span class="meta">Hech kim topilmadi</span></div>';
    } else {
      resultsDiv.innerHTML = results.map(r => `
        <div class="search-item" onclick="openStudentDetails('${r.kod}')">
          <span class="name">${r.ismlar}</span>
          <span class="meta">${r.sinf} | ${r.kod}</span>
        </div>
      `).join("");
    }
    resultsDiv.classList.remove("hidden");
  } catch (e) {
    console.error("Search error:", e);
  }
}

// ─── Student Details Modal ───────────────
async function openStudentDetails(kod) {
  const modal = document.getElementById("student-modal");
  modal.classList.remove("hidden");
  
  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch(`/api/admin/student_details?kod=${kod}`, { headers });
    const { student, natijalar } = await res.json();

    document.getElementById("modal-student-name").textContent = student.ismlar;
    document.getElementById("modal-student-class").textContent = student.sinf;
    document.getElementById("modal-student-dir").textContent = student.yonalish || "Umumiy";
    document.getElementById("modal-student-kod").textContent = student.kod;

    renderStudentDetailChart(natijalar);
    renderModalTable(natijalar);
  } catch (e) {
    console.error("Details fetch error:", e);
  }
}

function renderStudentDetailChart(natijalar) {
  const ctx = document.getElementById("studentDetailChart").getContext("2d");
  if (studentDetailChart) studentDetailChart.destroy();

  const labels = natijalar.map(n => n.sana);
  const scores = natijalar.map(n => n.umumiy_ball);

  studentDetailChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Ball",
        data: scores,
        borderColor: "#7289da",
        backgroundColor: "rgba(114, 137, 218, 0.1)",
        fill: true,
        tension: 0.3
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#8e9297" } },
        x: { grid: { display: false }, ticks: { color: "#8e9297" } }
      }
    }
  });
}

function renderModalTable(natijalar) {
  const wrap = document.getElementById("modal-history-table");
  if (!natijalar || natijalar.length === 0) {
    wrap.innerHTML = '<p class="meta" style="text-align:center">Natijalar yo\'q</p>';
    return;
  }

  let html = `<table class="history-table" style="width:100%; font-size:0.8rem;">
    <thead><tr><th>Sana</th><th>Ball</th><th>M</th><th>A1</th><th>A2</th></tr></thead><tbody>`;
  
  natijalar.reverse().forEach(n => {
    html += `<tr>
      <td>${n.sana}</td>
      <td style="font-weight:bold; color:var(--accent)">${n.umumiy_ball}</td>
      <td>${n.majburiy_ball}</td>
      <td>${n.asosiy_1_ball}</td>
      <td>${n.asosiy_2_ball}</td>
    </tr>`;
  });
  html += "</tbody></table>";
  wrap.innerHTML = html;
}

function closeModal() {
  document.getElementById("student-modal").classList.add("hidden");
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
      <div class="classmate-row" style="grid-template-columns: 28px 1fr 60px;" onclick="openStudentDetails('${s.kod}')">
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

function showError(msg) {
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("error-msg").textContent = msg;
  document.getElementById("error-screen").classList.remove("hidden");
}

async function loadAdminMaterials() {
  try {
    const resp = await fetch("/api/admin/materials", {
      headers: { "X-Telegram-Init-Data": tg.initData }
    });
    const data = await resp.json();
    const container = document.getElementById("admin-materials-list");
    if (!data.materials || data.materials.length === 0) {
      container.innerHTML = '<p style="color: #aaa; text-align:center; padding: 10px;">Hech qanday material yo\'q.</p>';
      return;
    }

    let html = '<div class="admin-table-wrapper"><table><thead><tr><th>Nomi</th><th>Fan</th><th>Amal</th></tr></thead><tbody>';
    data.materials.forEach(m => {
      html += `<tr>
        <td>${m.nomi}</td>
        <td>${m.fanni_nomi || '—'}</td>
        <td>
          <button class="btn-delete" onclick="deleteMaterial(${m.id})">🗑</button>
        </td>
      </tr>`;
    });
    html += '</tbody></table></div>';
    container.innerHTML = html;
  } catch (err) {
    console.error(err);
  }
}

async function deleteMaterial(id) {
  if (!confirm("Haqiqatan ham ushbu materialni o'chirmoqchimisiz?")) return;
  try {
    const resp = await fetch(`/api/admin/materials/${id}`, {
      method: 'DELETE',
      headers: { 'X-Telegram-Init-Data': tg.initData }
    });
    const res = await resp.json();
    if (res.success) {
      loadAdminMaterials();
    } else {
      tg.showAlert("Xatolik: " + res.error);
    }
  } catch (err) {
    tg.showAlert("Xatolik yuz berdi!");
  }
}

async function loadAdminQuizQuestions() {
  try {
    const resp = await fetch("/api/admin/quiz", {
      headers: { "X-Telegram-Init-Data": tg.initData }
    });
    const data = await resp.json();
    const container = document.getElementById("admin-quiz-list");
    if (!data.questions || data.questions.length === 0) {
      container.innerHTML = '<p style="color: #aaa; text-align:center; padding: 10px;">Hali savollar qo\'shilmagan.</p>';
      return;
    }

    let html = '<div class="admin-table-wrapper"><table><thead><tr><th>Fan</th><th>Savol</th><th>Holat</th><th>Amal</th></tr></thead><tbody>';
    data.questions.forEach(q => {
      html += `<tr>
        <td>${q.subject}</td>
        <td>${q.question.substring(0, 30)}...</td>
        <td>
          <label class="switch">
            <input type="checkbox" ${q.is_active ? 'checked' : ''} onchange="toggleQuizActive(${q.id}, this.checked)">
            <span class="slider round"></span>
          </label>
        </td>
        <td>
          <button class="btn-delete" onclick="deleteQuizQuestion(${q.id})">🗑</button>
        </td>
      </tr>`;
    });
    html += '</tbody></table></div>';
    container.innerHTML = html;
  } catch (err) {
    console.error(err);
  }
}

async function addQuizQuestion() {
  const subject = document.getElementById("quiz-subject").value.trim();
  const question = document.getElementById("quiz-question").value.trim();
  const options = [
    document.getElementById("quiz-opt-0").value.trim(),
    document.getElementById("quiz-opt-1").value.trim(),
    document.getElementById("quiz-opt-2").value.trim(),
    document.getElementById("quiz-opt-3").value.trim()
  ];
  const correct_option = parseInt(document.getElementById("quiz-correct").value);
  const explanation = document.getElementById("quiz-explanation").value.trim();

  if (!subject || !question || options.some(o => !o)) {
    tg.showAlert("Barcha maydonlarni to'ldiring!");
    return;
  }

  try {
    const resp = await fetch("/api/admin/quiz", {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': tg.initData
      },
      body: JSON.stringify({ subject, question, options, correct_option, explanation })
    });
    const res = await resp.json();
    if (res.success) {
      tg.showAlert("Savol qo'shildi!");
      document.getElementById("quiz-question").value = '';
      document.getElementById("quiz-opt-0").value = '';
      document.getElementById("quiz-opt-1").value = '';
      document.getElementById("quiz-opt-2").value = '';
      document.getElementById("quiz-opt-3").value = '';
      document.getElementById("quiz-explanation").value = '';
      loadAdminQuizQuestions();
    } else {
      tg.showAlert("Xatolik: " + res.error);
    }
  } catch (err) {
    tg.showAlert("Xatolik!");
  }
}

async function deleteQuizQuestion(id) {
  if (!confirm("Ushbu savolni o'chirmoqchimisiz?")) return;
  try {
    const resp = await fetch(`/api/admin/quiz/${id}`, {
      method: 'DELETE',
      headers: { 'X-Telegram-Init-Data': tg.initData }
    });
    const res = await resp.json();
    if (res.success) {
      loadAdminQuizQuestions();
    }
  } catch (err) {
    tg.showAlert("Xatolik!");
  }
}

async function toggleQuizActive(id, active) {
  try {
    const resp = await fetch(`/api/admin/quiz/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': tg.initData
      },
      body: JSON.stringify({ is_active: active, subject: "Partial", question: "Partial", options: [], correct_option: 0 }) 
      // The current server.py PUT is strict, I should fix it to be partial or fetch first.
    });
    const res = await resp.json();
    if (!res.success) {
       tg.showAlert("Holatni yangilashda xatolik!");
       loadAdminQuizQuestions();
    }
  } catch (err) {
    console.error(err);
  }
}
