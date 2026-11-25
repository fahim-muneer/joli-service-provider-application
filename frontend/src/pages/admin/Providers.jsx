import { useState } from "react";
import { Link } from "react-router-dom";
import { listProviders } from "../../api/admin";
import Button from "../../components/Button";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import StatusBadge from "../../components/StatusBadge";
import { useLoad } from "../../hooks";
import { ADMIN_PROVIDER_STATUS, formatDate, initials } from "../../utils/status";

const TABS = [
  ["under_review", "Needs review"],
  ["pending", "Not submitted"],
  ["approved", "Active"],
  ["rejected", "Rejected"],
  ["suspended", "Suspended"],
  ["", "All"],
];

// Figma "Service providers": title with a count line, then one white table.
export default function Providers() {
  const [status, setStatus] = useState("under_review");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState(""); // the search that was actually submitted
  const [page, setPage] = useState(1);
  const list = useLoad(() => listProviders({ status, search: query, page, pageSize: 20 }), [status, query, page]);
  const waiting = useLoad(() => listProviders({ status: "under_review", pageSize: 1 }).then((d) => d.count));

  const pick = (value) => { setStatus(value); setPage(1); };
  const doSearch = (e) => { e.preventDefault(); setQuery(search.trim()); setPage(1); };

  return (
    <>
      <div className="page-head">
        <h1>Service Providers</h1>
        <p>{list.status === "ready" ? `${list.data.count} providers` : "Loading…"}{waiting.status === "ready" ? ` · ${waiting.data} awaiting approval` : ""}</p>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map(([value, label]) => (
          <button key={value} type="button" role="tab" aria-selected={status === value} className={`tab ${status === value ? "tab--on" : ""}`} onClick={() => pick(value)}>{label}</button>
        ))}
      </div>

      <form className="filters row" onSubmit={doSearch}>
        <label className="grow">Search by name, phone or email<input value={search} onChange={(e) => setSearch(e.target.value)} /></label>
        <Button type="submit" size="small">Search</Button>
      </form>

      {list.status === "loading" && <Spinner label="Loading providers…" />}
      {list.status === "error" && <ErrorMessage message={list.error} onRetry={list.reload} />}
      {list.status === "ready" && list.data.results.length === 0 && <p className="empty">No providers here.</p>}
      {list.status === "ready" && list.data.results.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr><th>Provider</th><th>Phone</th><th>Email</th><th>Status</th><th>Documents</th><th>Applied</th><th>Action</th></tr>
            </thead>
            <tbody>
              {list.data.results.map((p) => (
                <tr key={p.id}>
                  <td><div className="who"><span className="avatar">{initials(p.full_name)}</span><span>{p.business_name || p.full_name}</span></div></td>
                  <td>{p.phone}{!p.is_phone_verified && <small className="muted" style={{ display: "block" }}>not verified</small>}</td>
                  <td>{p.email}</td>
                  <td><StatusBadge table={ADMIN_PROVIDER_STATUS} value={p.approval_status} /></td>
                  <td>{p.documents_count}{p.pending_documents_count > 0 && <small className="muted" style={{ display: "block" }}>{p.pending_documents_count} to review</small>}</td>
                  <td>{formatDate(p.applied_at)}</td>
                  <td><Link className="btn btn--ghost btn--small" to={`/admin/providers/${p.id}`}>View</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {list.status === "ready" && (list.data.previous || list.data.next) && (
        <div className="pager">
          <Button variant="ghost" size="small" disabled={!list.data.previous} onClick={() => setPage((n) => n - 1)}>Previous</Button>
          <span>Page {page} · {list.data.count} providers</span>
          <Button variant="ghost" size="small" disabled={!list.data.next} onClick={() => setPage((n) => n + 1)}>Next</Button>
        </div>
      )}
    </>
  );
}
