import { api } from "./client";
import { tokenStore } from "./tokenStore";

/** portal: "customer" | "provider" | "admin". Each login page sends its own, so an account
 *  can only sign in through the door it belongs to. Everyone signs in with phone + password.
 *  Returns the user. */
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

/** Phone OTP. Both calls need the user to be logged in (the backend knows the phone from the token).
 *  A first code is sent automatically at registration; "send" is only for re-sending. */
export const sendPhoneCode = () => api.post("/auth/verify-phone/send/").then((r) => r.data);
/** Resolves to { detail, user }: the user now has is_phone_verified = true. */
export const confirmPhoneCode = ({ otp }) => api.post("/auth/verify-phone/confirm/", { otp }).then((r) => r.data);

export const registerCustomer = (body) =>
  api.post("/auth/register/customer/", body, { skipAuth: true }).then((r) => r.data);
export const registerProvider = (body) =>
  api.post("/auth/register/provider/", body, { skipAuth: true }).then((r) => r.data);
