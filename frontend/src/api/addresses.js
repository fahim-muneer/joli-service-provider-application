import { api } from "./client";

export const listAddresses = () =>
  api.get("/locations/addresses/").then((r) => r.data);

export const createAddress = (payload) =>
  api.post("/locations/addresses/", payload).then((r) => r.data);

export const updateAddress = (id, payload) =>
  api.patch(`/locations/addresses/${id}/`, payload).then((r) => r.data);

export const deleteAddress = (id) =>
  api.delete(`/locations/addresses/${id}/`);

export const setDefaultAddress = (id) =>
  api.post(`/locations/addresses/${id}/default/`).then((r) => r.data);
