import { useState } from "react";
import { deleteDocument, listDocuments, uploadDocument } from "../../api/provider";
import { openProtectedFile } from "../../api/files";
import Button from "../../components/Button";
import AccountCard from "../../components/portal/AccountCard";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import StatusBadge from "../../components/StatusBadge";
import { useLoad } from "../../hooks";
import { getErrorMessage } from "../../utils/errors";
import { DOCUMENT_STATUS, formatDate } from "../../utils/status";

// The backend's document types. Only the ID proof is known here: add more [value, label] pairs
// to match ProviderDocument.DocumentType when you add them.
const TYPES = [["id_proof", "ID proof (Aadhaar, PAN, driving licence…)"]];

export default function Documents() {
  const docs = useLoad(listDocuments);
  const [form, setForm] = useState({ document_type: TYPES[0][0], file: null, expires_at: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [fileKey, setFileKey] = useState(0); // changing it empties the file input after an upload

  async function handleUpload(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const created = await uploadDocument(form);
      docs.setData([created, ...docs.data]);
      setForm((f) => ({ ...f, file: null, expires_at: "" }));
      setFileKey((k) => k + 1);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    setError("");
    try {
      await deleteDocument(id);
      docs.setData(docs.data.filter((d) => d.id !== id));
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  const view = (url) => openProtectedFile(url).catch((err) => setError(getErrorMessage(err)));

  return (
    <AccountCard>
<p className="muted">Upload an ID proof. An admin reviews it before your application can be approved.</p>

      <form className="form" onSubmit={handleUpload}>
        <label>
          Document type
          <select value={form.document_type} onChange={(e) => setForm((f) => ({ ...f, document_type: e.target.value }))}>
            {TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          File
          <input key={fileKey} type="file" accept=".pdf,.jpg,.jpeg,.png" required onChange={(e) => setForm((f) => ({ ...f, file: e.target.files[0] ?? null }))} />
        </label>
        <label>
          Expiry date (if any)
          <input type="date" value={form.expires_at} onChange={(e) => setForm((f) => ({ ...f, expires_at: e.target.value }))} />
        </label>
        <ErrorMessage message={error} />
        <Button type="submit" disabled={busy || !form.file}>{busy ? "Uploading…" : "Upload"}</Button>
      </form>

      <h2 className="section-title">Your documents</h2>
      {docs.status === "loading" && <Spinner />}
      {docs.status === "error" && <ErrorMessage message={docs.error} onRetry={docs.reload} />}
      {docs.status === "ready" && docs.data.length === 0 && <p className="empty">No documents yet.</p>}
      {docs.status === "ready" && docs.data.length > 0 && (
        <ul className="rows">
          {docs.data.map((d) => (
            <li key={d.id} className="row">
              <div>
                <strong>{d.original_name || "Document"}</strong>
                <span className="muted"> · uploaded {formatDate(d.uploaded_at)}{d.expires_at ? ` · expires ${formatDate(d.expires_at)}` : ""}</span>
                {d.status === "rejected" && d.rejection_reason && <div className="alert alert--error">Rejected: {d.rejection_reason}</div>}
              </div>
              <StatusBadge table={DOCUMENT_STATUS} value={d.status} />
              <Button variant="ghost" size="small" onClick={() => view(d.download_url)}>View</Button>
              {d.status !== "approved" && <Button variant="ghost" size="small" onClick={() => remove(d.id)}>Delete</Button>}
            </li>
          ))}
        </ul>
      )}
    </AccountCard>
  );
}
