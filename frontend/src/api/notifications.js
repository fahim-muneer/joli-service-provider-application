
import { api } from "./client";

const data = (promise) => promise.then((r) => r.data);

/** Get notifications belonging to the logged-in user. */
export const listNotifications = ({ unreadOnly = false } = {}) =>
  data(
    api.get("/notifications/", {
      params: unreadOnly ? { unread: "true" } : {},
    }),
  );

/** Get the unread notification count. */
export const getUnreadNotificationCount = () =>
  data(api.get("/notifications/unread-count/"));

/** Mark one notification as read. */
export const markNotificationRead = (id) =>
  data(api.post(`/notifications/${id}/read/`));

/** Mark all notifications as read. */
export const markAllNotificationsRead = () =>
  data(api.post("/notifications/read-all/"));
