import { useState } from "react";
import { Link } from "react-router-dom";
import { getMe, listDocuments, listMyAreas, listMyServices, setOnline, submitForReview } from "../../api/provider";
import Button from "../../components/Button";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import StatusBadge from "../../components/StatusBadge";
import { useLoad } from "../../hooks";
import { PROVIDER_STATUS } from "../../utils/status";
import { getErrorMessage } from "../../utils/errors";

const STATUS_TEXT = {
  pending: "Finish the steps below, then submit your application for review.",
  under_review: "We are reviewing your application. You can go online once it is approved.",
  approved: "You are approved. Switch online to start receiving customers.",
  rejected: "Your application was rejected. Fix the issues, then submit it again.",
  suspended: "Your account is suspended. Please contact support.",
};

const STEPS = [
  ["/provider/profile", "Profile", "Business name, bio, experience, languages"],
  ["/provider/documents", "Documents", "Upload your ID proof"],
  ["/provider/services", "Services & prices", "What you offer and what you charge"],
  ["/provider/areas", "Service areas", "Where you can work"],
  ["/provider/schedule", "Schedule", "The days and hours you are free"],
];

// Figma "Dashboard": four summary cards, then a card with the main content.
// The booking numbers in the design need the bookings feature, so these cards show what the backend has today.
const loadDashboard = () => Promise.all([getMe(), listMyServices(), listMyAreas(), listDocuments()]);

export default function Overview() {
  const dash = useLoad(loadDashboard);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (dash.status === "loading") return <Spinner label="Loading your dashboard…" />;
  if (dash.status === "error") return <ErrorMessage message={dash.error} onRetry={dash.reload} />;

  const [p, myServices, myAreas, docs] = dash.data;
  const setProfile = (next) => dash.setData([next, myServices, myAreas, docs]);

  async function run(action) {
    setError("");
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const submit = () => run(async () => setProfile(await submitForReview()));
  const toggleOnline = () => run(async () => {
    const state = await setOnline(!p.is_available);
    setProfile({ ...p, is_available: state.is_available, approval_status: state.approval_status });
  });

  const submittable = p.approval_status === "pending" || p.approval_status === "rejected";
  const activeServices = myServices.filter((s) => s.is_active).length;
  const approvedDocs = docs.filter((d) => d.status === "approved").length;

  return (
    <>
      <div className="stats">
        <div className="stat"><small>Application status</small><div><StatusBadge table={PROVIDER_STATUS} value={p.approval_status} /></div><span>{p.is_available ? "Online now" : "Offline"}</span></div>
        <div className="stat"><small>Services offered</small><strong>{activeServices}</strong><span>{activeServices === 1 ? "service" : "services"} switched on</span></div>
        <div className="stat"><small>Areas covered</small><strong>{myAreas.length}</strong><span>areas customers can find you in</span></div>
        <div className="stat"><small>Documents</small><strong>{approvedDocs}/{docs.length}</strong><span>approved by admin</span></div>
      </div>

      <div className="panel">
        <div className="panel__head">
          <h2>Hello, {p.business_name || p.full_name}</h2>
          <StatusBadge table={PROVIDER_STATUS} value={p.approval_status} />
        </div>
        <p>{STATUS_TEXT[p.approval_status]}</p>
        {p.approval_status === "rejected" && p.rejection_reason && <p className="alert alert--error">Reason: {p.rejection_reason}</p>}

        {submittable && (
          <>
            {p.submission_blockers.length > 0 ? (
              <ul className="checklist">{p.submission_blockers.map((b) => <li key={b}>{b}</li>)}</ul>
            ) : (
              <p className="notice">Everything is ready. Submit your application.</p>
            )}
            {!p.is_phone_verified && <p><Link to="/provider/verify-phone">Verify your phone now</Link></p>}
            <div><Button disabled={!p.can_submit || busy} onClick={submit}>{busy ? "Submitting…" : "Submit for review"}</Button></div>
          </>
        )}

        {p.approval_status === "approved" && (
          <label className="switch">
            <input type="checkbox" checked={p.is_available} disabled={busy} onChange={toggleOnline} />
            <span>{p.is_available ? "You are online" : "You are offline"}</span>
          </label>
        )}
        <ErrorMessage message={error} />
      </div>

      <div className="panel">
        <h2>Set up your account</h2>
        <div className="cards">
          {STEPS.map(([to, title, text]) => (
            <Link key={to} to={to} className="card"><strong>{title}</strong><span>{text}</span></Link>
          ))}
        </div>
      </div>

      <div className="panel">
        <h2>Recent bookings</h2>
        <p className="muted">Your bookings will appear here once the bookings feature is added.</p>
      </div>
    </>
  );
}
