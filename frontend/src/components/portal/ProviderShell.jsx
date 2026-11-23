import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import NavIcon from "./NavIcons";

// Figma "provider" page: white sidebar, dark-blue top bar, white title bar, pale-blue content.
const NAV = [
  ["/provider", "Dashboard", "home", true],
  ["/provider/requests", "Requests", "list"],
  ["/provider/schedule", "Schedule", "calendar"],
  ["/provider/earnings", "Earnings", "wallet"],
  ["/provider/notifications", "Notifications", "bell"],
  ["/provider/profile", "My profile", "user"],
  ["/provider/payment", "Payment", "card"],
];

const TITLES = [
  ["/provider/schedule", "Schedules"],
  ["/provider/profile", "Account"],
  ["/provider/services", "Account"],
  ["/provider/areas", "Account"],
  ["/provider/documents", "Account"],
  ["/provider/requests", "Requests"],
  ["/provider/earnings", "Earnings"],
  ["/provider/notifications", "Notifications"],
  ["/provider/payment", "Payment"],
];

// The Account tabs share the "My profile" sidebar item.
const ACCOUNT = ["/provider/profile", "/provider/services", "/provider/areas", "/provider/documents"];

export default function ProviderShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const title = TITLES.find(([p]) => pathname.startsWith(p))?.[1] ?? "Dashboard";

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
            const forceActive = to === "/provider/profile" && ACCOUNT.some((p) => pathname.startsWith(p));
            return (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive || forceActive ? "is-active" : "")}>
                <NavIcon name={icon} /> <span>{label}</span>
              </NavLink>
            );
          })}
        </nav>
        <button type="button" className="shell__logout" onClick={handleLogout}><NavIcon name="logout" /> <span>Logout</span></button>
      </aside>

      <div className="shell__body">
        <header className="topbar">
          <NavLink to="/provider/notifications" className="topbar__bell" aria-label="Notifications"><NavIcon name="bell" /></NavLink>
          <span className="topbar__avatar" aria-hidden="true" />
          <span className="topbar__hello">Hello, {user.full_name}</span>
        </header>
        <div className="titlebar"><h1>{title}</h1></div>
        <main id="content" className="shell__main"><Outlet /></main>
      </div>
    </div>
  );
}
