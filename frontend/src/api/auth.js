import { api } from "./client";
import { tokenStore } from "./tokenStore";

/** portal: "customer" | "provider" | "admin": each app sends its own, so an account
 *  can only sign in where it belongs. Returns the user. */
export async function login({ phone, password, portal }) {
  const { data } = await api.post("/auth/login/", { phone, password, portal }, { skipAuth: true });
  tokenStore.set({ access: data.access, refresh: data.refresh });
  return data.user;
}

export async function logout() {
  const refresh = tokenStore.getRefresh();
  try {
    if (refresh) await api.post("/auth/logout/", { refresh }, { skipAuth: true });
  } finally {
    tokenStore.clear(); // sign out locally even if the server call failed
  }
}

export const getProfile = () => api.get("/auth/profile/").then((r) => r.data);
export const updateProfile = (body) => api.patch("/auth/profile/", body).then((r) => r.data);

export const registerCustomer = (body) =>
  api.post("/auth/register/customer/", body, { skipAuth: true }).then((r) => r.data);
export const registerProvider = (body) =>
  api.post("/auth/register/provider/", body, { skipAuth: true }).then((r) => r.data);
