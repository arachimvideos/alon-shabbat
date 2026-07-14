const runtimeConfig = window.__APP_CONFIG__ || {};
const API_BASE = runtimeConfig.API_BASE || import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function request(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let message = "אירעה שגיאה";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.json();
}

function authHeaders() {
  const token = localStorage.getItem("adminToken");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function listParashot() {
  return request("/api/parashot");
}

export function listTags() {
  return request("/api/tags");
}

export function listArticles(filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => params.append(key, item));
    } else if (value !== undefined && value !== null && value !== "") {
      params.set(key, value);
    }
  });
  return request(`/api/articles?${params.toString()}`);
}

export function getArticle(id) {
  return request(`/api/articles/${id}`);
}

export function getAuthStatus() {
  return request("/api/auth/status");
}

export function checkAdminSession() {
  return request("/api/auth/session", {
    headers: authHeaders(),
  });
}

export function loginAdmin(password) {
  const formData = new FormData();
  formData.set("password", password);
  return request("/api/auth/login", {
    method: "POST",
    body: formData,
  });
}

export function createArticle(formData) {
  return request("/api/articles", {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
}

export function updateArticle(id, formData) {
  return request(`/api/articles/${id}`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
}

export function fileUrl(articleId) {
  return `${API_BASE}/api/articles/${articleId}/file`;
}

export function articlePdfUrl(articleId) {
  return `${API_BASE}/api/articles/${articleId}/pdf`;
}

export function imageUrl(articleId) {
  return `${API_BASE}/api/articles/${articleId}/image`;
}
