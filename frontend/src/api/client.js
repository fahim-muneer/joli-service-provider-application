import axios from "axios";
import { tokenStore } from "./tokenStore";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

/** The client every API module uses. */
export const api = axios.create({ baseURL: API_BASE_URL, timeout: 15000 });

/** Used only to refresh tokens. A separate instance so the refresh call can never
 *  trigger the refresh logic below (no loops). */
export const rawApi = axios.create({ baseURL: API_BASE_URL, timeout: 15000 });

let onSessionExpired = null;
/** AuthContext registers a callback here so the UI can react when a refresh fails. */
export function setSessionExpiredHandler(handler) {
  onSessionExpired = handler;
}

// Add the access token. Requests marked { skipAuth: true } (login, register, ...) never carry one.
api.interceptors.request.use((config) => {
  const access = tokenStore.getAccess();
  if (access && !config.skipAuth) {
    config.headers.Authorization = `Bearer ${access}`;
  }
  return config;
});

// The backend ROTATES refresh tokens: every refresh returns a new refresh token and
// kills the old one. So two refreshes must never run at once: concurrent 401s share one.
let refreshing = null;

function refreshTokens() {
  if (!refreshing) {
    refreshing = rawApi
      .post("/auth/token/refresh/", { refresh: tokenStore.getRefresh() })
      .then(({ data }) => {
        tokenStore.set({ access: data.access, refresh: data.refresh });
        return data.access;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

// On a 401: refresh once, then repeat the original request with the new token.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error;
    const canRetry =
      response?.status === 401 &&
      config &&
      !config.skipAuth &&
      !config._retried &&
      Boolean(tokenStore.getRefresh());
    if (!canRetry) return Promise.reject(error);

    config._retried = true;
    try {
      const access = await refreshTokens();
      config.headers.Authorization = `Bearer ${access}`;
      return api(config);
    } catch {
      tokenStore.clear();
      if (onSessionExpired) onSessionExpired();
      return Promise.reject(error); // the original 401
    }
  },
);
