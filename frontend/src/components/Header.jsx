import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { PROVIDER_APP_URL } from "../config";
import { useAuth } from "../context/useAuth";
import AccountMenu from "./AccountMenu";
import AnnouncementBar from "./AnnouncementBar";
import LocationButton from "./LocationButton";
import SearchBar from "./SearchBar";

export default function Header() {
  const { user, loading, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const close = () => setOpen(false);

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  return (
    <header className="header">
      <div className="header__bar">
        <div className="page header__inner">
          <Link to="/" className="logo" onClick={close}>Joli</Link>

          <button
            type="button"
            className="header__toggle"
            aria-expanded={open}
            aria-controls="header-panel"
            onClick={() => setOpen((v) => !v)}
          >
            <span className="visually-hidden">Menu</span>
            <span aria-hidden="true">{open ? "✕" : "☰"}</span>
          </button>

          <div id="header-panel" className={`header__panel ${open ? "is-open" : ""}`}>
            {loading ? null : user ? (
              <AccountMenu user={user} onLogout={handleLogout} onNavigate={close} />
            ) : (
              <Link to="/login" className="btn btn--yellow" onClick={close}>
                Login
              </Link>
            )}

            <SearchBar onSearch={close} />

            <nav className="nav" aria-label="Main">
              <NavLink to="/" end onClick={close}>Home</NavLink>

              {(!user || user.role === "customer") && (
                <NavLink to="/bookings" onClick={close}>My Bookings</NavLink>
              )}

              <NavLink to="/services" onClick={close}>Services</NavLink>

              {user?.role !== "provider" && (
                PROVIDER_APP_URL ? (
                  <a href={PROVIDER_APP_URL}>Become a Provider</a>
                ) : (
                  <NavLink to="/provider/register" onClick={close}>
                    Become a Provider
                  </NavLink>
                )
              )}
            </nav>

            <LocationButton onClick={close} />
          </div>
        </div>
      </div>
      <AnnouncementBar />
    </header>
  );
}
