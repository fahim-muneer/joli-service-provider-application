import { useCallback, useEffect, useState } from "react";
import {
  listNotifications,
  markAllNotificationsAsRead,
  markNotificationAsRead,
} from "../../api/notifications";
import Button from "../../components/Button";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import { getErrorMessage } from "../../utils/errors";
import "../../styles/provider-notifications.css";

function formatDate(value) {
  if (!value) return "Date unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Date unavailable";

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatType(type) {
  if (!type) return "Notification";

  return type
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default function Notifications() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [markingAll, setMarkingAll] = useState(false);

  const loadNotifications = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setError("");

    try {
      const data = await listNotifications();
      setNotifications(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const data = await listNotifications();

        if (active) {
          setNotifications(Array.isArray(data) ? data : []);
          setError("");
        }
      } catch (err) {
        if (active) setError(getErrorMessage(err));
      } finally {
        if (active) setLoading(false);
      }
    }

    load();

    const intervalId = window.setInterval(load, 15000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const unreadCount = notifications.filter(
    (notification) => !notification.is_read,
  ).length;

  async function handleMarkRead(id) {
    setBusyId(id);
    setActionError("");

    try {
      await markNotificationAsRead(id);

      setNotifications((current) =>
        current.map((notification) =>
          notification.id === id
            ? { ...notification, is_read: true }
            : notification,
        ),
      );
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  async function handleMarkAllRead() {
    setMarkingAll(true);
    setActionError("");

    try {
      await markAllNotificationsAsRead();

      setNotifications((current) =>
        current.map((notification) => ({
          ...notification,
          is_read: true,
        })),
      );
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setMarkingAll(false);
    }
  }

  if (loading) {
    return <Spinner label="Loading notifications…" />;
  }

  if (error && notifications.length === 0) {
    return (
      <ErrorMessage
        message={error}
        onRetry={() => loadNotifications(true)}
      />
    );
  }

  return (
    <section className="provider-notifications-page">
      <div className="provider-notifications-page__intro">
        <div>
          <h2>Your notifications</h2>
          <p>
            Updates about booking requests and activity in your provider
            account.
          </p>
        </div>

        <div className="provider-notifications-page__actions">
          <Button
            disabled={loading}
            onClick={() => loadNotifications(true)}
          >
            Refresh
          </Button>

          <Button
            disabled={unreadCount === 0 || markingAll}
            onClick={handleMarkAllRead}
          >
            {markingAll ? "Please wait…" : "Mark all as read"}
          </Button>
        </div>
      </div>

      <ErrorMessage message={error || actionError} />

      <div className="provider-notifications-page__summary">
        <strong>{unreadCount}</strong>
        <span>unread notification{unreadCount === 1 ? "" : "s"}</span>
      </div>

      {notifications.length === 0 ? (
        <div className="provider-notification-empty">
          <h2>No notifications yet</h2>
          <p>
            When customers send you booking requests or your account receives
            an update, you will see it here.
          </p>
        </div>
      ) : (
        <div className="provider-notifications-list">
          {notifications.map((notification) => (
            <article
              key={notification.id}
              className={`provider-notification ${
                notification.is_read
                  ? "provider-notification--read"
                  : "provider-notification--unread"
              }`}
            >
              <div className="provider-notification__content">
                <div className="provider-notification__heading">
                  <span className="provider-notification__type">
                    {formatType(notification.type)}
                  </span>

                  {!notification.is_read && (
                    <span className="provider-notification__unread">
                      New
                    </span>
                  )}
                </div>

                <h3>{notification.title}</h3>
                <p>{notification.body}</p>

                <time dateTime={notification.created_at}>
                  {formatDate(notification.created_at)}
                </time>
              </div>

              {!notification.is_read && (
                <div className="provider-notification__actions">
                  <Button
                    disabled={busyId === notification.id}
                    onClick={() => handleMarkRead(notification.id)}
                  >
                    {busyId === notification.id
                      ? "Please wait…"
                      : "Mark as read"}
                  </Button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
