// PathForge — Reports page
PathForge.auth.redirectIfNotAuthed();
document.getElementById("nav").innerHTML = PathForge.renderNavbar("reports");
PathForge.attachLogout();

const user = PathForge.auth.getUser();
document.getElementById("email-target").value = user.email;

const REPORTS = [
  {
    id: "progress",
    icon: "📊",
    title: "Progress Report",
    desc: "Snapshot of your stats, streak, XP, and milestone-by-milestone progress.",
    needsRoadmap: false,
    needsCompletion: false,
  },
  {
    id: "bundle",
    icon: "📚",
    title: "Resource Bundle",
    desc: "All curated resources from a roadmap, organized by milestone — like a study guide.",
    needsRoadmap: true,
    needsCompletion: false,
  },
  {
    id: "certificate",
    icon: "🏆",
    title: "Completion Certificate",
    desc: "Branded landscape certificate. Unlocks when a roadmap reaches 100%.",
    needsRoadmap: true,
    needsCompletion: true,
  },
];

let allRoadmaps = [];

async function load() {
  try {
    allRoadmaps = await PathForge.api.listRoadmaps();
    const sel = document.getElementById("roadmap-select");
    if (allRoadmaps.length === 0) {
      sel.innerHTML = `<option value="">No roadmaps yet — create one first</option>`;
    } else {
      sel.innerHTML = allRoadmaps.map(rm =>
        `<option value="${rm.id}" data-pct="${rm.progress_percent}">${PathForge.escapeHtml(rm.title)} (${rm.progress_percent}%)</option>`
      ).join("");
    }
    renderCards();
    sel.addEventListener("change", renderCards);
  } catch (err) {
    PathForge.toast(err.message, "error");
  }
}

function renderCards() {
  const sel = document.getElementById("roadmap-select");
  const roadmapId = sel.value;
  const selectedOpt = sel.options[sel.selectedIndex];
  const pct = selectedOpt ? parseFloat(selectedOpt.dataset.pct || "0") : 0;

  document.getElementById("report-cards").innerHTML = REPORTS.map(r => {
    const disabled = (r.needsRoadmap && !roadmapId) || (r.needsCompletion && pct < 100);
    let warn = "";
    if (r.needsRoadmap && !roadmapId) warn = "Select a roadmap above";
    else if (r.needsCompletion && pct < 100) warn = `Roadmap is ${pct}% — complete it to unlock`;
    return `
      <div class="card" style="opacity:${disabled ? 0.5 : 1};">
        <div style="font-size:36px;margin-bottom:6px;">${r.icon}</div>
        <h3 style="font-size:18px;margin-bottom:6px;">${r.title}</h3>
        <p class="text-muted text-sm" style="margin-bottom:16px;line-height:1.5;">${r.desc}</p>
        ${warn ? `<p class="text-xs" style="color:var(--warm);margin-bottom:12px;">⚠️ ${warn}</p>` : ""}
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn btn-primary btn-sm" data-action="download" data-id="${r.id}" ${disabled ? "disabled" : ""}>
            ⬇️ Download PDF
          </button>
          <button class="btn btn-ghost btn-sm" data-action="email" data-id="${r.id}" ${disabled ? "disabled" : ""}>
            📧 Email me
          </button>
        </div>
      </div>
    `;
  }).join("");

  document.querySelectorAll('[data-action="download"]').forEach(b => {
    b.addEventListener("click", () => downloadReport(b.dataset.id));
  });
  document.querySelectorAll('[data-action="email"]').forEach(b => {
    b.addEventListener("click", () => openEmailModal(b.dataset.id));
  });
}

async function downloadReport(reportId) {
  const roadmapId = document.getElementById("roadmap-select").value;
  const token = PathForge.auth.getToken();
  let url;
  if (reportId === "progress") {
    url = `http://localhost:8000/api/reports/progress.pdf${roadmapId ? `?roadmap_id=${roadmapId}` : ""}`;
  } else if (reportId === "bundle") {
    url = `http://localhost:8000/api/reports/bundle.pdf?roadmap_id=${roadmapId}`;
  } else {
    url = `http://localhost:8000/api/reports/certificate.pdf?roadmap_id=${roadmapId}`;
  }

  PathForge.showLoader("Generating PDF…");
  try {
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `pathforge_${reportId}.pdf`;
    a.click();
    URL.revokeObjectURL(a.href);
    PathForge.toast("Downloaded!");
  } catch (err) {
    PathForge.toast(err.message, "error");
  } finally {
    PathForge.hideLoader();
  }
}

let pendingEmailReport = null;

function openEmailModal(reportId) {
  pendingEmailReport = reportId;
  document.getElementById("email-modal").classList.add("show");
}

document.getElementById("email-cancel").addEventListener("click", () => {
  document.getElementById("email-modal").classList.remove("show");
});

document.getElementById("email-send").addEventListener("click", async () => {
  const roadmapId = document.getElementById("roadmap-select").value;
  const target = document.getElementById("email-target").value.trim();
  if (!target) { PathForge.toast("Email required", "error"); return; }

  document.getElementById("email-modal").classList.remove("show");
  PathForge.showLoader("Sending email…");
  try {
    const r = await PathForge.api.emailReport({
      report_type: pendingEmailReport,
      roadmap_id: roadmapId ? parseInt(roadmapId) : null,
      to_email: target,
    });
    PathForge.toast(r.message || "Sent!");
  } catch (err) {
    PathForge.toast(err.message, "error");
  } finally {
    PathForge.hideLoader();
  }
});

load();