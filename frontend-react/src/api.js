let tokenGetter = null;
export function setTokenGetter(getter) { tokenGetter = getter; }
export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
async function request(path, options = {}) {
  const {timeoutMs = 120000, ...fetchOptions} = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers = new Headers(fetchOptions.headers);
    if(tokenGetter){const token=await tokenGetter();if(token)headers.set("Authorization","Bearer "+token);}
    const response = await fetch(path, { ...fetchOptions, headers, credentials: "same-origin", signal: controller.signal });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status === 401 && !path.includes("/auth/")) window.dispatchEvent(new Event("session-expired"));
      const detail = Array.isArray(data?.detail) ? data.detail.map(x => x.msg).join(" ") : data?.detail;
      throw new ApiError(detail || "The request could not finish. Please try again.", response.status);
    }
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(error.name === "AbortError" ? "This is taking too long. Refresh to check its status before retrying." : "Cannot reach SimplyDoc. Check your connection and try again.", 0);
  } finally { clearTimeout(timer); }
}
const post = (path, body, timeoutMs) => request(path, { timeoutMs, method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
export const api = {
  linkClerk: password => post("/api/auth/clerk/link", {password}),
  providers: () => request("/api/auth/providers"),
  startGoogle: (link = false) => post("/api/auth/google/start", { link }),
  health: () => request("/api/health"), me: () => request("/api/auth/me"),
  login: (email, password) => post("/api/auth/login", { email, password }),
  signup: (email, password) => post("/api/auth/signup", { email, password }),
  logout: () => post("/api/auth/logout"),
  listDocuments: () => request("/api/documents"),
  getDocument: id => request("/api/documents/" + id),
  uploadDocument: file => { const body = new FormData(); body.append("file", file); return request("/api/documents/upload", { method: "POST", body }); },
  sample: () => post("/api/documents/sample"),
  reviewSource: (id,sections,revision) => post("/api/documents/"+id+"/source-review",{sections,revision}),
  retry: id => post("/api/documents/" + id + "/retry"),
  deleteDocument: id => request("/api/documents/" + id, { method: "DELETE" }),
  getChatHistory: id => request("/api/documents/" + id + "/chat"),
  sendChatMessage: (id, message) => post("/api/documents/" + id + "/chat", { message }, 330000),
};
