import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

export const apiClient = {
  login: (username, password) =>
    api.post("/api/auth/login/", { username, password }),
  logout: () => api.post("/api/auth/logout/"),
  session: () => api.get("/api/auth/session/"),
  linkedinStatus: () => api.get("/api/linkedin/status/"),
  generateLinkedInPost: (prompt) =>
    api.post("/api/linkedin/preview/", { prompt }),
  publishLinkedInPost: (text) => api.post("/api/linkedin/publish/", { text }),
  connectLinkedIn: () => {
    const frontendOrigin = encodeURIComponent(window.location.origin);
    window.location.assign(
      `${API_BASE}/link/linkedin/?frontend_origin=${frontendOrigin}`,
    );
  },
};

export default api;
