/**
 * Knovex AI - Frontend Client
 */

const API_BASE = "/api/v1";
let authToken = localStorage.getItem("knovex_token");
let currentConversationId = null;
let pollTimer = null;

// DOM Elements
const authSection = document.getElementById("authSection");
const dashboardSection = document.getElementById("dashboardSection");
const navUserSection = document.getElementById("navUserSection");
const tenantBadge = document.getElementById("tenantBadge");
const userBadge = document.getElementById("userBadge");
const logoutBtn = document.getElementById("logoutBtn");
const authAlert = document.getElementById("authAlert");

const loginTabBtn = document.getElementById("loginTabBtn");
const registerTabBtn = document.getElementById("registerTabBtn");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");

const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const uploadProgress = document.getElementById("uploadProgress");
const uploadStatusText = document.getElementById("uploadStatusText");
const docList = document.getElementById("docList");
const docCount = document.getElementById("docCount");

const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const newChatBtn = document.getElementById("newChatBtn");
const rerankToggle = document.getElementById("rerankToggle");

// ---------------------------------------------------------
// Auth Tab Switching
// ---------------------------------------------------------

loginTabBtn.addEventListener("click", () => {
  loginTabBtn.classList.add("active");
  registerTabBtn.classList.remove("active");
  loginForm.style.display = "block";
  registerForm.style.display = "none";
  authAlert.style.display = "none";
});

registerTabBtn.addEventListener("click", () => {
  registerTabBtn.classList.add("active");
  loginTabBtn.classList.remove("active");
  registerForm.style.display = "block";
  loginForm.style.display = "none";
  authAlert.style.display = "none";
});

// ---------------------------------------------------------
// API Helper
// ---------------------------------------------------------

async function apiRequest(endpoint, options = {}) {
  const headers = options.headers || {};
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  options.headers = headers;

  const res = await fetch(`${API_BASE}${endpoint}`, options);
  if (res.status === 401) {
    logout();
    throw new Error("Session expired. Please log in again.");
  }
  return res;
}

// ---------------------------------------------------------
// Login & Register Handlers
// ---------------------------------------------------------

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("loginEmail").value;
  const password = document.getElementById("loginPassword").value;

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");

    setSession(data);
  } catch (err) {
    showAlert(err.message);
  }
});

registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const organization_name = document.getElementById("regOrg").value;
  const full_name = document.getElementById("regFullName").value;
  const email = document.getElementById("regEmail").value;
  const password = document.getElementById("regPassword").value;

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ organization_name, full_name, email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Registration failed");

    setSession(data);
  } catch (err) {
    showAlert(err.message);
  }
});

function showAlert(msg) {
  authAlert.textContent = msg;
  authAlert.style.display = "block";
}

function setSession(tokenData) {
  authToken = tokenData.access_token;
  localStorage.setItem("knovex_token", authToken);
  localStorage.setItem("knovex_user", JSON.stringify(tokenData));
  initDashboard();
}

logoutBtn.addEventListener("click", logout);

async function logout() {
  try {
    if (authToken) {
      await apiRequest("/auth/logout", { method: "POST" });
    }
  } catch (e) {}
  authToken = null;
  localStorage.removeItem("knovex_token");
  localStorage.removeItem("knovex_user");
  if (pollTimer) clearInterval(pollTimer);
  showAuthView();
}

function showAuthView() {
  authSection.style.display = "flex";
  dashboardSection.style.display = "none";
  navUserSection.style.display = "none";
}

// ---------------------------------------------------------
// Dashboard Initialization
// ---------------------------------------------------------

async function initDashboard() {
  const user = JSON.parse(localStorage.getItem("knovex_user") || "{}");
  tenantBadge.textContent = user.tenant_id ? `Tenant: ${user.tenant_id.slice(0, 8)}...` : "Tenant";
  userBadge.textContent = user.email || "User";

  authSection.style.display = "none";
  dashboardSection.style.display = "flex";
  navUserSection.style.display = "flex";

  await loadDocuments();
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(loadDocuments, 5000);
}

// ---------------------------------------------------------
// Documents & Upload
// ---------------------------------------------------------

async function loadDocuments() {
  if (!authToken) return;
  try {
    const res = await apiRequest("/documents");
    if (!res.ok) return;
    const docs = await res.json();
    docCount.textContent = docs.length;

    if (docs.length === 0) {
      docList.innerHTML = `<div class="empty-state">No documents uploaded yet.</div>`;
      return;
    }

    docList.innerHTML = docs
      .map(
        (d) => `
      <div class="doc-card" id="doc-${d.id}">
        <div class="doc-meta">
          <span class="doc-name" title="${d.filename}">${d.filename}</span>
          <span class="doc-sub">${(d.file_size / 1024).toFixed(1)} KB • ${d.total_chunks} chunks</span>
        </div>
        <div class="doc-actions">
          <button class="btn btn-secondary btn-sm" onclick="deleteDoc('${d.id}')" title="Delete">✕</button>
        </div>
      </div>
    `
      )
      .join("");
  } catch (err) {
    console.error("Failed to load documents:", err);
  }
}

window.deleteDoc = async function (docId) {
  if (!confirm("Are you sure you want to delete this document and its vectors?")) return;
  try {
    await apiRequest(`/documents/${docId}`, { method: "DELETE" });
    await loadDocuments();
  } catch (err) {
    alert("Delete failed: " + err.message);
  }
};

// File Upload Drag & Drop
dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) uploadFile(fileInput.files[0]);
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});

async function uploadFile(file) {
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);

  uploadProgress.style.display = "flex";
  uploadStatusText.textContent = `Uploading ${file.name}...`;

  try {
    const res = await apiRequest("/documents/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");

    uploadStatusText.textContent = `Processing and chunking ${file.name}...`;
    setTimeout(() => {
      uploadProgress.style.display = "none";
      loadDocuments();
    }, 2000);
  } catch (err) {
    alert("Upload failed: " + err.message);
    uploadProgress.style.display = "none";
  }
}

// ---------------------------------------------------------
// Chat Interaction
// ---------------------------------------------------------

newChatBtn.addEventListener("click", () => {
  currentConversationId = null;
  chatMessages.innerHTML = `
    <div class="chat-welcome">
      <div class="welcome-icon">⚡</div>
      <h4>New Chat Session</h4>
      <p>Ask a question about your indexed tenant documents below.</p>
    </div>
  `;
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;

  chatInput.value = "";
  appendMessage("user", message);

  // Loading state placeholder
  const loadingRow = appendMessage("assistant", "Searching hybrid index, reranking, and querying Grok...");
  sendBtn.disabled = true;

  try {
    const res = await apiRequest("/chat/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        conversation_id: currentConversationId,
        rerank: rerankToggle.checked,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "RAG query failed");

    currentConversationId = data.conversation_id;
    loadingRow.remove();
    appendAssistantMessage(data);
  } catch (err) {
    loadingRow.remove();
    appendMessage("assistant", `Error: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
  }
});

function appendMessage(role, text) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;
  row.innerHTML = `<div class="message-bubble">${escapeHtml(text)}</div>`;
  chatMessages.appendChild(row);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return row;
}

function appendAssistantMessage(data) {
  const row = document.createElement("div");
  row.className = "message-row assistant";

  let citationsHtml = "";
  if (data.citations && data.citations.length > 0) {
    citationsHtml = `
      <div class="citations-box">
        <div class="citations-title">
          <span>✓ Validated Sources (${data.citations.length})</span>
        </div>
        ${data.citations
          .map(
            (c) => `
          <div class="citation-item">
            <div class="citation-header">${escapeHtml(c.filename)} (Page ${c.page_number})</div>
            <div class="citation-snippet">"${escapeHtml(c.snippet)}"</div>
          </div>
        `
          )
          .join("")}
      </div>
    `;
  }

  row.innerHTML = `
    <div class="message-bubble">${escapeHtml(data.answer)}</div>
    ${citationsHtml}
  `;
  chatMessages.appendChild(row);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Auto-login check on page load
if (authToken) {
  initDashboard();
} else {
  showAuthView();
}
