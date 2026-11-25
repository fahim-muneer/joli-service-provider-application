import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { approveProvider, getProvider, reinstateProvider, rejectProvider, reviewDocument, suspendProvider } from "../../api/admin";
import { openProtectedFile } from "../../api/files";
import Button from "../../components/Button";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import StatusBadge from "../../components/StatusBadge";
import { useLoad } from "../../hooks";
import { getErrorMessage } from "../../utils/errors";
import { ADMIN_PROVIDER_STATUS, DOCUMENT_STATUS, formatDate } from "../../utils/status";

const DOC_LABEL = { id_proof: "Government ID" };
const docName = (type) => DOC_LABEL[type] ?? type.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** Approve / reject one uploaded document. Rejecting needs a reason. */
function DocumentReview({ doc, onReviewed, onError }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  async function decide(decision) {
    if (decision === "rejected" && !reason.trim()) {
      onError("Write a reason before rejecting a document.");
      return;
    }
    setBusy(true);
    try {
      await reviewDocument(doc.id, { decision, reason });
      await onReviewed();
    } catch (err) {
      onError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="docrow">
      <div className="docrow__top">
        <div>
          <strong>{docName(doc.document_type)}</strong>
          <small>{doc.original_name} · uploaded {formatDate(doc.uploaded_at)}{doc.expires_at ? ` · expires ${formatDate(doc.expires_at)}` : ""}</small>
        </div>
        <StatusBadge table={DOCUMENT_STATUS} value={doc.status} />
        <Button variant="ghost" size="small" onClick={() => openProtectedFile(doc.download_url).catch((e) => onError(getErrorMessage(e)))}>View ↗</Button>
      </div>
      {doc.status === "rejected" && doc.rejection_reason && <small>Rejected: {doc.rejection_reason}</small>}
      {doc.status === "pending" && (
        <div className="row">
          <input className="grow" placeholder="Reason (needed to reject)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button size="small" disabled={busy} onClick={() => decide("approved")}>Approve</Button>
          <Button variant="ghost" size="small" disabled={busy} onClick={() => decide("rejected")}>Reject</Button>
        </div>
      )}
    </li>
  );
}

const Check = ({ ok, children }) => <li style={{ color: ok ? "#1c7a52" : "#b42318" }}>{ok ? "✓" : "✗"} {children}</li>;

// Figma "Provider application detail": header card, two columns (details + documents + activity,
// then the decision card).
export default function ProviderDetail() {
  const { id } = useParams();
  const provider = useLoad(() => getProvider(id), [id]);
  const [text, setText] = useState(""); // the note or reason for the provider-level action
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (provider.status === "loading") return <Spinner label="Loading provider…" />;
  if (provider.status === "error") return <><Link to="/admin/providers" className="back-link">← Service Providers</Link><ErrorMessage message={provider.error} onRetry={provider.reload} /></>;

  const p = provider.data;
  const status = p.approval_status;
  const approvedDocs = p.documents.filter((d) => d.status === "approved").length;

  async function act(action, { needsReason = false } = {}) {
    setError("");
    if (needsReason && !text.trim()) {
      setError("Please write a reason first.");
      return;
    }
    setBusy(true);
    try {
      provider.setData(await action());
      setText("");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <p className="muted"><Link to="/admin/providers" className="back-link">Service Providers</Link> / Applications / APP-{p.id}</p>
      <div className="page-head row" style={{ justifyContent: "space-between" }}>
        <div><h1>Provider application</h1><p>Review credentials and coverage before activating a professional.</p></div>
        <Link className="btn btn--ghost" to="/admin/providers">Back to applications</Link>
      </div>

      <div className="panel">
        <div className="panel__head">
          <h2 style={{ fontSize: 22 }}>{p.business_name || p.full_name}</h2>
          <StatusBadge table={ADMIN_PROVIDER_STATUS} value={status} />
        </div>
        <p className="muted">
          APP-{p.id}{p.experience_years ? ` · ${p.experience_years} years experience` : ""} · Applied {formatDate(p.applied_at)}
        </p>
        {status === "rejected" && p.rejection_reason && <p className="alert alert--error">Rejected: {p.rejection_reason}</p>}
      </div>

      <div className="ad-grid">
        <div>
          <div className="panel">
            <h2>Personal &amp; service information</h2>
            <dl className="facts">
              <div><dt>Mobile number</dt><dd>{p.phone} {p.is_phone_verified ? "" : "(not verified)"}</dd></div>
              <div><dt>Primary area</dt><dd>{p.areas[0] ? `${p.areas[0].name}, ${p.areas[0].city_name}` : "—"}</dd></div>
              <div><dt>Email</dt><dd>{p.email || "—"}</dd></div>
              <div><dt>Experience</dt><dd>{p.experience_years ? `${p.experience_years} years` : "—"}</dd></div>
              <div><dt>Languages</dt><dd>{p.languages?.length ? p.languages.join(", ") : "—"}</dd></div>
              <div><dt>Requested services</dt><dd>{p.services.length ? p.services.map((s) => s.service_name).join(" · ") : "—"}</dd></div>
            </dl>
            {p.bio && <p>{p.bio}</p>}
          </div>

          <div className="panel">
            <h2>Verification documents</h2>
            <p className="muted">{approvedDocs} of {p.documents.length} documents verified</p>
            {p.documents.length === 0 ? <p className="muted">No documents uploaded yet.</p> : (
              <ul className="rows">
                {p.documents.map((d) => <DocumentReview key={d.id} doc={d} onReviewed={provider.reload} onError={setError} />)}
              </ul>
            )}
          </div>

          <div className="panel">
            <h2>Application activity</h2>
            {p.status_history.length === 0 ? <p className="muted">No changes yet.</p> : (
              <ul className="timeline">
                {p.status_history.map((h) => (
                  <li key={h.id}><span>{formatDate(h.changed_at)}</span>{h.from_status} → {h.to_status} by {h.changed_by_name ?? "system"}{h.reason || h.internal_note ? ` · ${h.reason || h.internal_note}` : ""}</li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div>
          <div className="panel decision">
            <h2>Ready for your decision</h2>
            <ul className="timeline" style={{ listStyle: "none" }}>
              <Check ok={p.is_phone_verified}>Phone number verified</Check>
              <Check ok={p.documents.length > 0 && approvedDocs === p.documents.length}>{approvedDocs}/{p.documents.length} documents verified</Check>
              <Check ok={p.areas.length > 0}>Service area available</Check>
              <Check ok={p.services.length > 0}>Services listed</Check>
            </ul>

            {(status === "pending" || status === "rejected") ? (
              <p className="muted">Waiting for the provider to submit the application.</p>
            ) : (
              <>
                {status === "under_review" && (
                  <div className="info-box"><strong>Approval activates the profile</strong>The provider can receive bookings in approved areas. At least one ID proof must be approved first.</div>
                )}
                <label className="stack">
                  {status === "under_review" ? "Note (for approval) or reason (needed to reject)" : status === "approved" ? "Reason (needed to suspend)" : "Note (optional)"}
                  <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} />
                </label>
                {status === "under_review" && (
                  <>
                    <Button disabled={busy} onClick={() => act(() => approveProvider(p.id, text))}>Approve provider</Button>
                    <Button className="btn--danger" disabled={busy} onClick={() => act(() => rejectProvider(p.id, text), { needsReason: true })}>Reject application</Button>
                  </>
                )}
                {status === "approved" && <Button className="btn--danger" disabled={busy} onClick={() => act(() => suspendProvider(p.id, text), { needsReason: true })}>Suspend provider</Button>}
                {status === "suspended" && <Button disabled={busy} onClick={() => act(() => reinstateProvider(p.id, text))}>Reinstate provider</Button>}
                <p className="muted" style={{ fontSize: 12 }}>Each decision records the reviewer, time and reason.</p>
              </>
            )}
            <ErrorMessage message={error} />
          </div>

          {p.internal_admin_note && (
            <div className="panel"><h2>Internal note</h2><div className="info-box" style={{ background: "#f6f8fb" }}>{p.internal_admin_note}</div><p className="muted" style={{ fontSize: 12 }}>Visible to admins only.</p></div>
          )}

          <div className="panel">
            <h2>Services offered</h2>
            {p.services.length === 0 ? <p className="muted">None yet.</p> : (
              <ul className="rows">
                {p.services.map((s) => (
                  <li key={s.id} className="row"><span><strong>{s.service_name}</strong> <small className="muted">{s.category_name}</small></span><span>₹{Number(s.custom_price).toLocaleString("en-IN")}</span>{!s.is_active && <span className="status status--muted">Off</span>}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
