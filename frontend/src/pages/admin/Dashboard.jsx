import { Link } from "react-router-dom";
import { listProviders } from "../../api/admin";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import StatusBadge from "../../components/StatusBadge";
import { useLoad } from "../../hooks";
import { ADMIN_PROVIDER_STATUS, formatDate, initials } from "../../utils/status";

// Figma "Admin dashboard": summary cards and a list. Booking and revenue figures need the bookings
// feature, so this shows the provider numbers the backend has today.
const count = (status) => listProviders({ status, pageSize: 1 }).then((d) => d.count);
const load = () => Promise.all([count(""), count("under_review"), count("approved"), count("suspended"), listProviders({ status: "under_review", pageSize: 5 })]);

export default function AdminDashboard() {
  const dash = useLoad(load);

  if (dash.status === "loading") return <Spinner label="Loading dashboard…" />;
  if (dash.status === "error") return <ErrorMessage message={dash.error} onRetry={dash.reload} />;

  const [total, review, active, suspended, waiting] = dash.data;

  return (
    <>
      <div className="page-head"><h1>Dashboard</h1><p>An overview of the marketplace.</p></div>
      <div className="stats">
        <div className="stat"><small>Total providers</small><strong>{total}</strong><span>all applications</span></div>
        <div className="stat"><small>Awaiting approval</small><strong>{review}</strong><span>need your review</span></div>
        <div className="stat"><small>Active providers</small><strong>{active}</strong><span>can receive bookings</span></div>
        <div className="stat"><small>Suspended</small><strong>{suspended}</strong><span>currently blocked</span></div>
      </div>

      <div className="panel">
        <div className="panel__head"><h2>Applications waiting for review</h2><Link to="/admin/providers">View all</Link></div>
        {waiting.results.length === 0 ? <p className="muted">Nothing is waiting. Well done.</p> : (
          <ul className="rows">
            {waiting.results.map((p) => (
              <li key={p.id} className="row">
                <div className="who"><span className="avatar">{initials(p.full_name)}</span><div><strong>{p.business_name || p.full_name}</strong><small className="muted" style={{ display: "block" }}>{p.phone} · applied {formatDate(p.applied_at)}</small></div></div>
                <StatusBadge table={ADMIN_PROVIDER_STATUS} value={p.approval_status} />
                <Link className="btn btn--ghost btn--small" to={`/admin/providers/${p.id}`}>View</Link>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="panel"><h2>Bookings and revenue</h2><p className="muted">These figures will appear here once the bookings feature is added.</p></div>
    </>
  );
}
