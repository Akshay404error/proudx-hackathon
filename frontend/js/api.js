// PathForge — shared API client & auth utilities

const API_BASE = (() => {
  const meta = document.querySelector('meta[name="api-base"]');
  if (meta) return meta.getAttribute("content");
  if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
    return "http://localhost:8000/api";
  }
  return "/api";
})();

const TOKEN_KEY = "pathforge_token";
const USER_KEY = "pathforge_user";

const auth = {
  getToken() { return localStorage.getItem(TOKEN_KEY); },
  getUser() {
    try { return JSON.parse(localStorage.getItem(USER_KEY)); }
    catch { return null; }
  },
  setSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
  isAuthed() { return !!this.getToken(); },
  redirectIfNotAuthed() {
    if (!this.isAuthed()) location.href = "login.html";
  },
};

async function apiRequest(path, { method = "GET", body, auth: needsAuth = true, query } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (needsAuth) {
    const tok = auth.getToken();
    if (!tok) throw new Error("Not authenticated");
    headers["Authorization"] = `Bearer ${tok}`;
  }

  let url = `${API_BASE}${path}`;
  if (query) {
    const params = new URLSearchParams(query);
    url += `?${params.toString()}`;
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    auth.clear();
    location.href = "login.html";
    throw new Error("Session expired");
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data.detail || data.error || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

const api = {
  health: () => apiRequest("/health", { auth: false }),

  // OTP-gated auth
  signupRequest: (data) => apiRequest("/auth/signup/request", { method: "POST", body: data, auth: false }),
  signupVerify: (data) => apiRequest("/auth/signup/verify", { method: "POST", body: data, auth: false }),
  loginRequest: (data) => apiRequest("/auth/login/request", { method: "POST", body: data, auth: false }),
  loginVerify: (data) => apiRequest("/auth/login/verify", { method: "POST", body: data, auth: false }),
  otpResend: (data) => apiRequest("/auth/otp/resend", { method: "POST", body: data, auth: false }),

  me: () => apiRequest("/profile/me"),
  updateMe: (params) => apiRequest("/profile/me", { method: "PATCH", query: params }),
  publicProfile: (username) => apiRequest(`/profile/u/${username}`, { auth: false }),
  publicRoadmaps: (username) => apiRequest(`/profile/u/${username}/roadmaps`, { auth: false }),
  mentorLearners: () => apiRequest("/profile/mentor/learners"),

  chat: (message) => apiRequest("/chat/", { method: "POST", body: { message } }),
  clearChatHistory: () => apiRequest("/chat/history", { method: "DELETE" }),

  generateRoadmap: (data) => apiRequest("/roadmaps/generate", { method: "POST", body: data }),
  listRoadmaps: () => apiRequest("/roadmaps/"),
  getRoadmap: (id) => apiRequest(`/roadmaps/${id}`),
  deleteRoadmap: (id) => apiRequest(`/roadmaps/${id}`, { method: "DELETE" }),
  toggleVisibility: (id, isPublic) =>
    apiRequest(`/roadmaps/${id}/visibility`, { method: "PATCH", query: { is_public: isPublic } }),

  completeLesson: (lessonId) => apiRequest("/progress/lesson/complete", { method: "POST", body: { lesson_id: lessonId } }),
  uncompleteLesson: (lessonId) => apiRequest("/progress/lesson/uncomplete", { method: "POST", body: { lesson_id: lessonId } }),
  getStreak: () => apiRequest("/progress/streak"),

  // Resource verification + feedback
  verifyResources: (lessonId) => apiRequest("/resources/verify", { method: "POST", body: { lesson_id: lessonId } }),
  submitFeedback: (data) => apiRequest("/resources/feedback", { method: "POST", body: data }),

  // Reports
  emailReport: (data) => apiRequest("/reports/email", { method: "POST", body: data }),
};

function toast(msg, type = "success") {
  let container = document.querySelector(".toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateX(20px)"; }, 3000);
  setTimeout(() => el.remove(), 3400);
}

function showLoader(msg = "Loading…") {
  let el = document.querySelector(".loader-fullscreen");
  if (!el) {
    el = document.createElement("div");
    el.className = "loader-fullscreen";
    el.innerHTML = `<div class="spinner"></div><p></p>`;
    document.body.appendChild(el);
  }
  el.querySelector("p").textContent = msg;
  el.classList.add("show");
}
function hideLoader() {
  const el = document.querySelector(".loader-fullscreen");
  if (el) el.classList.remove("show");
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function renderNavbar(activePage) {
  const user = auth.getUser();
  const links = user
    ? `
      <a href="dashboard.html" class="${activePage === 'dashboard' ? 'active' : ''}">Dashboard</a>
      <a href="chat.html" class="${activePage === 'chat' ? 'active' : ''}">AI Coach</a>
      <a href="reports.html" class="${activePage === 'reports' ? 'active' : ''}">Reports</a>
      ${user.role === 'mentor' || user.role === 'institution'
        ? `<a href="mentor.html" class="${activePage === 'mentor' ? 'active' : ''}">Learners</a>` : ''}
      <a href="profile.html?u=${encodeURIComponent(user.username)}" class="${activePage === 'profile' ? 'active' : ''}">Profile</a>
      <a href="#" id="logout-btn" class="hide-mobile">Logout</a>
    `
    : `
      <a href="login.html">Log in</a>
      <a href="register.html" class="btn btn-primary btn-sm">Get Started</a>
    `;

  return `
    <nav class="navbar">
      <div class="nav-inner">
        <a href="${user ? 'dashboard.html' : 'index.html'}" class="logo">PathForge</a>
        <div class="nav-links">${links}</div>
      </div>
    </nav>`;
}

function attachLogout() {
  const btn = document.getElementById("logout-btn");
  if (btn) btn.addEventListener("click", (e) => {
    e.preventDefault();
    auth.clear();
    location.href = "index.html";
  });
}

window.PathForge = { api, auth, toast, showLoader, hideLoader, escapeHtml, renderNavbar, attachLogout };