import { NavLink } from "react-router-dom";

// Figma "Account" page: tabs (Setup / Document / Bank Details) above a white card.
// Our tabs follow what the backend stores. Bank details are not in the backend yet.
const TABS = [
  ["/provider/profile", "Profile"],
  ["/provider/services", "Services"],
  ["/provider/areas", "Areas"],
  ["/provider/documents", "Document"],
];

export default function AccountCard({ children }) {
  return (
    <div className="acct">
      <nav className="acct__tabs" aria-label="Account sections">
        {TABS.map(([to, label]) => <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "is-active" : "")}>{label}</NavLink>)}
        <span title="Coming soon">Bank Details</span>
      </nav>
      <div className="acct__body">{children}</div>
    </div>
  );
}
