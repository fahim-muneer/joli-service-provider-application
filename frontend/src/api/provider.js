import { api } from "./client";

// The logged-in provider's own data: /providers/me/...
const data = (promise) => promise.then((r) => r.data);

export const getMe = () => data(api.get("/providers/me/"));
export const updateMe = (body) => data(api.patch("/providers/me/", body));
export const submitForReview = () => data(api.post("/providers/me/submit/"));
export const setOnline = (is_available) => data(api.patch("/providers/me/availability/", { is_available }));

export const listDocuments = () => data(api.get("/providers/me/documents/"));
export function uploadDocument({ document_type, file, expires_at }) {
  const form = new FormData();
  form.append("document_type", document_type);
  form.append("file", file);
  if (expires_at) form.append("expires_at", expires_at);
  return data(api.post("/providers/me/documents/", form));
}
export const deleteDocument = (id) => api.delete(`/providers/me/documents/${id}/`);

export const listMyServices = () => data(api.get("/providers/me/services/"));
export const offerService = (body) => data(api.post("/providers/me/services/", body));
export const updateMyService = (id, body) => data(api.patch(`/providers/me/services/${id}/`, body));
export const removeMyService = (id) => api.delete(`/providers/me/services/${id}/`);

export const listMyAreas = () => data(api.get("/providers/me/areas/"));
/** Replaces the WHOLE selection with these area ids. */
export const replaceMyAreas = (areas) => data(api.put("/providers/me/areas/", { areas }));

export const listSchedule = (params) => data(api.get("/providers/me/schedule/", { params }));
export const addSchedule = (body) => data(api.post("/providers/me/schedule/", body));
export const deleteSchedule = (id) => api.delete(`/providers/me/schedule/${id}/`);
