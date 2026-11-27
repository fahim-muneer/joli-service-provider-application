import { api } from "./client";

export const listAddresses = () =>
  api.get("/locations/addresses/").then((r) => r.data);

export const createAddress = (body) =>
  api.post("/locations/addresses/", body).then((r) => r.data);

export const updateAddress = (id, body) =>
  api.patch(`/locations/addresses/${id}/`, body).then((r) => r.data);

export const deleteAddress = (id) =>
  api.delete(`/locations/addresses/${id}/`);

export const setDefaultAddress = (id) =>
  api.post(`/locations/addresses/${id}/default/`).then((r) => r.data);
