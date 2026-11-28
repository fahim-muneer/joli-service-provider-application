
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { getUnreadNotificationCount } from "../../api/notifications";
import { useAuth } from "../../context/useAuth";
import NavIcon from "./NavIcons";

const NAV = [
  ["/provider", "Dashboard", "home", true],
  ["/provider/requests", "Requests", "list"],
  ["/provider/bookings", "My Bookings", "list"],
  ["/provider/schedule", "Schedule", "calendar"],
  ["/provider/earnings", "Earnings", "wallet"],
  ["/provider/notifications", "Notifications", "bell"],
  ["/provider/profile", "My profile", "user"],
  ["/provider/payment", "Payment", "card"],
];

const TITLES = [
  ["/provider/schedule", "Schedules"],
  ["/provider/bookings", "My Bookings"],
  ["/provider/profile", "Account"],
  ["/provider/services", "Account"],
  ["/provider/areas", "Account"],
  ["/provider/documents", "Account"],
  ["/provider/requests", "Requests"],
  ["/provider/earnings", "Earnings"],
  ["/provider/notifications", "Notifications"],
  ["/provider/payment", "Payment"],
];

const ACCOUNT = [
  "/provider/profile",
  "/provider/services",
  "/provider/areas",
  "/provider/documents",
];

export default function ProviderShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    let active = true;

    async function loadUnreadCount() {
      try {
        const data = await getUnreadNotificationCount();

        if (active) {
          setUnreadCount(data.unread_count ?? 0);
        }
      } catch (error) {
        console.error("Unable to load notification count:", error);
      }
    }

    loadUnreadCount();

    const intervalId = window.setInterval(loadUnreadCount, 15000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const title =
    TITLES.find(([path]) => pathname.startsWith(path))?.[1] ?? "Dashboard";

  async function handleLogout() {
    await logout();
    navigate("/provider/login");
  }

  return (
    <div className="portal portal--provider shell">
      <aside className="shell__side">
        <div className="shell__logo">Joli</div>

        <nav className="shell__nav" aria-label="Provider menu">
          {NAV.map(([to, label, icon, end]) => {
            const forceActive =
              to === "/provider/profile" &&
              ACCOUNT.some((path) => pathname.startsWith(path));

            return (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  isActive || forceActive ? "is-active" : ""
                }
              >
                <NavIcon name={icon} />
                <span>{label}</span>
              </NavLink>
            );
          })}
        </nav>

        <button
          type="button"
          className="shell__logout"
          onClick={handleLogout}
        >
          <NavIcon name="logout" />
          <span>Logout</span>
        </button>
      </aside>

      <div className="shell__body">
        <header className="topbar">
          <NavLink
            to="/provider/notifications"
            className="topbar__bell"
            aria-label={`Notifications${
              unreadCount > 0 ? `, ${unreadCount} unread` : ""
            }`}
          >
          <span style={{ fontSize: "24px", color: "#facc15" }}>🔔</span>
          {unreadCount > 0 && (
              <span className="topbar__bell-count">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </NavLink>

          <span className="topbar__avatar" aria-hidden="true" />
          <span className="topbar__hello">
            Hello, {user.full_name}
          </span>
        </header>

        <div className="titlebar">
          <h1>{title}</h1>
        </div>

        <main id="content" className="shell__main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
