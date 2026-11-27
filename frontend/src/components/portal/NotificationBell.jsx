
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getUnreadNotificationCount } from "../../api/notifications";
import NavIcon from "./NavIcons";

export default function NotificationBell({ to, className = "" }) {
  const [count, setCount] = useState(0);

  const refreshCount = useCallback(async () => {
    try {
      const data = await getUnreadNotificationCount();
      setCount(Number(data.unread_count) || 0);
    } catch {
      // Keep the previous count if a temporary request fails.
    }
  }, []);

  useEffect(() => {
    refreshCount();

    const interval = setInterval(refreshCount, 30000);

    return () => clearInterval(interval);
  }, [refreshCount]);

  return (
    <Link
      to={to}
      className={`topbar__bell notification-bell ${className}`}
      aria-label={
        count > 0
          ? `Notifications, ${count} unread`
          : "Notifications"
      }
    >
      <NavIcon name="bell" size={21} />

      {count > 0 && (
        <span className="notification-bell__count">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </Link>
  );
}

