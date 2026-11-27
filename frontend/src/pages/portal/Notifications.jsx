
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  listNotifications,
  markNotificationRead,
  markAllNotificationsRead,
} from "../../api/notifications";
import { useLoad } from "../../hooks";
import NavIcon from "../../components/portal/NavIcons";

function formatDate(value) {
  if (!value) return "";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "";

  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function getIcon(type) {
  if (type?.startsWith("booking")) return "calendar";
  if (type?.startsWith("job")) return "tool";
  if (type?.startsWith("provider")) return "user";
  return "bell";
}

function getDestination(notification, basePath) {
  if (notification.booking) {
    if (basePath === "/provider") return "/provider/requests";
    if (basePath === "/admin") return "/admin/bookings";
    return "/bookings";
  }

  if (notification.type?.startsWith("provider")) {
    if (basePath === "/provider") return "/provider/profile";
    if (basePath === "/admin") return "/admin/providers";
  }

  return null;
}

export default function Notifications({ basePath }) {
  const navigate = useNavigate();

  const notifications = useLoad(listNotifications, []);

  const [busyId, setBusyId] = useState(null);
  const [markingAll, setMarkingAll] = useState(false);
  const [actionError, setActionError] = useState("");

  const items = Array.isArray(notifications.data)
    ? notifications.data
    : notifications.data?.results ?? [];

  const unreadCount = items.filter((item) => !item.is_read).length;

  
async function handleMarkRead(id) {
  setBusyId(id);
  setActionError("");

  try {
    await markNotificationRead(id);

    const current = notifications.data;
    const list = Array.isArray(current)
      ? current
      : current?.results ?? [];

    const updated = list.map((item) =>
      item.id === id
        ? { ...item, is_read: true, read_at: new Date().toISOString() }
        : item
    );

    notifications.setData(
      Array.isArray(current)
        ? updated
        : { ...current, results: updated }
    );
  } catch (error) {
    setActionError(
      error.response?.data?.detail || "Unable to mark notification as read."
    );
  } finally {
    setBusyId(null);
  }
}

async function handleMarkAllRead() {
  setMarkingAll(true);
  setActionError("");

  try {
    await markAllNotificationsRead();

    const current = notifications.data;
    const list = Array.isArray(current)
      ? current
      : current?.results ?? [];

    const updated = list.map((item) => ({
      ...item,
      is_read: true,
      read_at: item.read_at || new Date().toISOString(),
    }));

    notifications.setData(
      Array.isArray(current)
        ? updated
        : { ...current, results: updated }
    );
  } catch (error) {
    setActionError(
      error.response?.data?.detail || "Unable to mark all as read."
    );
  } finally {
    setMarkingAll(false);
  }
}


  async function handleOpen(notification) {
    if (!notification.is_read) {
      await handleMarkRead(notification.id);
    }

    const destination = getDestination(notification, basePath);

    if (destination) {
      navigate(destination);
    }
  }

  return (
    <section className="notifications-page">
      <div className="notifications-page__header">
        <div>
          <h2>Notifications</h2>
          <p>Stay updated with your latest activities.</p>
        </div>

        <button
          type="button"
          className="btn btn--ghost"
          onClick={handleMarkAllRead}
          disabled={unreadCount === 0 || markingAll}
        >
          {markingAll ? "Updating..." : "Mark all as read"}
        </button>
      </div>

      {unreadCount > 0 && (
        <p className="notifications-page__count">
          {unreadCount} unread notification{unreadCount !== 1 ? "s" : ""}
        </p>
      )}

      {actionError && (
        <p className="notifications-page__error" role="alert">
          {actionError}
        </p>
      )}

      {notifications.status === "loading" && (
        <div className="notifications-page__state">
          Loading notifications...
        </div>
      )}

      {notifications.status === "error" && (
        <div className="notifications-page__state" role="alert">
          <p>{notifications.error}</p>
          <button
            className="btn btn--primary"
            onClick={notifications.reload}
          >
            Retry
          </button>
        </div>
      )}

      {notifications.status === "ready" && items.length === 0 && (
        <div className="notifications-page__empty">
          <NavIcon name="bell" size={32} />
          <h3>No notifications yet</h3>
          <p>We'll notify you when something important happens.</p>
        </div>
      )}

      {notifications.status === "ready" && items.length > 0 && (
        <div className="notifications-list">
          {items.map((notification) => (
            <article
              key={notification.id}
              className={`notification-item ${
                notification.is_read ? "" : "is-unread"
              }`}
            >
              <button
                type="button"
                className="notification-item__open"
                onClick={() => handleOpen(notification)}
              >
                <span className="notification-item__icon">
                  <NavIcon name={getIcon(notification.type)} size={20} />
                </span>

                <span className="notification-item__content">
                  <strong>{notification.title}</strong>
                  <span>{notification.body}</span>
                  <small>{formatDate(notification.created_at)}</small>
                </span>

                {!notification.is_read && (
                  <span
                    className="notification-item__dot"
                    aria-label="Unread"
                  />
                )}
              </button>

              {!notification.is_read && (
                <button
                  type="button"
                  className="notification-item__mark"
                  disabled={busyId === notification.id}
                  onClick={() => handleMarkRead(notification.id)}
                >
                  {busyId === notification.id
                    ? "Updating..."
                    : "Mark as read"}
                </button>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
