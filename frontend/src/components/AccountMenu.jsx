import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

export default function AccountMenu({ user, onLogout, onNavigate }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => {
      if (e.type === "keydown" && e.key !== "Escape") return;
      if (e.type === "mousedown" && ref.current?.contains(e.target)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const go = () => {
    setOpen(false);
    onNavigate?.();
  };

  return (
    <div className="account" ref={ref}>
      <button type="button" className="btn btn--yellow" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((v) => !v)}>
        Account
      </button>
      {open && (
        <div className="account__menu" role="menu">
          <span className="account__name">{user.full_name}</span>
          <Link role="menuitem" to="/account" onClick={go}>My Account</Link>
          <Link role="menuitem" to="/bookings" onClick={go}>My Bookings</Link>
          <button type="button" role="menuitem" onClick={() => { go(); onLogout(); }}>Log out</button>
        </div>
      )}
    </div>
  );
}
