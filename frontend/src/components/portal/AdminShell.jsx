import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import NavIcon from "./NavIcons";
import NotificationBell from "./NotificationBell";

// Figma "admin" page: white sidebar with WORKSPACE label, search bar and profile on a white top bar.
// Only "Service Providers" has a screen so far; the rest open a "coming soon" page.
const NAV = [
  ["/admin", "Dashboard", "grid", true],
  ["/admin/providers", "Service Providers", "users"],
  ["/admin/customers", "Customers", "user"],
  ["/admin/categories", "Categories", "grid"],
  ["/admin/services", "Services", "tool"],
  ["/admin/areas", "Areas", "pin"],
  ["/admin/bookings", "Bookings", "calendar"],
  ["/admin/reviews", "Reviews & Ratings", "star"],
  ["/admin/payments", "Collections & Payouts", "wallet"],
  ["/admin/notifications", "Notifications", "bell"],
  ["/admin/settings", "Settings", "settings"],
];

const initials = (name = "") => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");

export default function AdminShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/admin/login");
  }

  return (
    <div className="portal portal--admin shell">
      <aside className="shell__side">
        <div className="shell__brand">
          <span className="shell__mark" aria-hidden="true"><NavIcon name="home2" size={16} /></span>
          <span><strong>Joli</strong><small>ADMIN PORTAL</small></span>
        </div>
        <div className="shell__section">WORKSPACE</div>
        <nav className="shell__nav" aria-label="Admin menu">
          {NAV.map(([to, label, icon, end]) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "is-active" : "")}>
              <NavIcon name={icon} /> <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <button type="button" className="shell__logout" onClick={handleLogout}><NavIcon name="logout" /> <span>Logout</span></button>
      </aside>

      <div className="shell__body">
        <header className="topbar">
          <div className="topbar__search"><NavIcon name="search" size={15} /> <span>Search bookings, people, services…</span></div>
            <NotificationBell to="/admin/notifications" />
          <span className="topbar__avatar topbar__avatar--initials" aria-hidden="true">{initials(user.full_name)}</span>
          <span className="topbar__who"><strong>{user.full_name}</strong><small>Super Admin</small></span>
        </header>
        <main id="content" className="shell__main"><Outlet /></main>
      </div>
    </div>
  );
}
