import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

export const mediaUrl = (path) => new URL(path, API_BASE).toString();

export const apiClient = {
  login: (username, password) =>
    api.post("/api/auth/login/", { username, password }),
  logout: () => api.post("/api/auth/logout/"),
  session: () => api.get("/api/auth/session/"),
  linkedinStatus: () => api.get("/api/linkedin/status/"),
  generateLinkedInPost: (prompt) =>
    api.post("/api/linkedin/preview/", { prompt }),
  linkedinPosts: () => api.get("/api/linkedin/posts/"),
  deleteLinkedInPosts: (postIds) =>
    api.delete("/api/linkedin/posts/", {
      data: postIds === null ? { all: true } : { ids: postIds },
    }),
  uploadLinkedInImage: (file) => {
    const formData = new FormData();
    formData.append("image", file);
    return api.post("/api/linkedin/upload-image/", formData);
  },
  publishLinkedInPost: (text, imageUrl, prompt) =>
    api.post("/api/linkedin/publish/", {
      text,
      image_url: imageUrl,
      prompt,
    }),
  connectLinkedIn: () => {
    const frontendOrigin = encodeURIComponent(window.location.origin);
    window.location.assign(
      `${API_BASE}/link/linkedin/?frontend_origin=${frontendOrigin}`,
    );
  },
};

export default api;
