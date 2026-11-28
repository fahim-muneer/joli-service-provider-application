import { api } from "./client";

export const listNotifications = () =>
  api.get("/notifications/").then((response) => response.data);

export const getUnreadNotificationCount = () =>
  api.get("/notifications/unread-count/").then((response) => response.data);

export const markNotificationAsRead = (id) =>
  api.post(`/notifications/${id}/read/`).then((response) => response.data);

export const markAllNotificationsAsRead = () =>
  api.post("/notifications/read-all/").then((response) => response.data);
