import { api } from "./client";
import { clean } from "./params";

export const createBooking = (body) =>
  api.post("/bookings/", body).then((r) => r.data);

export const listBookings = ({ status, scope, page, pageSize } = {}) =>
  api
    .get("/bookings/", {
      params: clean({ status, scope, page, page_size: pageSize }),
    })
    .then((r) => r.data);

export const getBooking = (id) =>
  api.get(`/bookings/${id}/`).then((r) => r.data);

export const cancelBooking = (id, body) =>
  api.post(`/bookings/${id}/cancel/`, body).then((r) => r.data);
