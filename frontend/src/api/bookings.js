import { api } from "./client";

export const createBooking = (payload) =>
  api.post("/bookings/", payload).then((r) => r.data);

export const listBookings = (params = {}) =>
  api.get("/bookings/", { params }).then((r) => r.data);

export const getBooking = (id) =>
  api.get(`/bookings/${id}/`).then((r) => r.data);

export const cancelBooking = (id, payload) =>
  api.post(`/bookings/${id}/cancel/`, payload).then((r) => r.data);

export const getCancelReasons = () =>
  api.get("/bookings/cancel-reasons/").then((r) => r.data);

// Provider booking requests
export const listProviderRequests = () =>
  api.get("/bookings/provider/requests/").then((r) => r.data);

export const acceptProviderRequest = (id) =>
  api.post(`/bookings/provider/requests/${id}/accept/`).then((r) => r.data);

export const declineProviderRequest = (id, reason = "") =>
  api.post(`/bookings/provider/requests/${id}/decline/`, { reason }).then((r) => r.data);
// Provider's accepted bookings
export const listProviderBookings = (params = {}) =>
  api.get("/bookings/provider/bookings/", { params }).then((r) => r.data);

export const getProviderBooking = (id) =>
  api.get(`/bookings/provider/bookings/${id}/`).then((r) => r.data);

export const startProviderBooking = (id, code) =>
  api.post(`/bookings/provider/bookings/${id}/start/`, { code }).then((r) => r.data);

export const completeProviderBooking = (id, note = "") =>
  api.post(`/bookings/provider/bookings/${id}/complete/`, { note }).then((r) => r.data);

export const cancelProviderBooking = (id, payload) =>
  api.post(`/bookings/provider/bookings/${id}/cancel/`, payload).then((r) => r.data);