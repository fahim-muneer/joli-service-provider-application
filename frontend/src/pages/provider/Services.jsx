import { useMemo, useState } from "react";
import { listServices } from "../../api/catalog";
import { listMyServices, offerService, removeMyService, updateMyService } from "../../api/provider";
import Button from "../../components/Button";
import AccountCard from "../../components/portal/AccountCard";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import { useLoad } from "../../hooks";
import { getErrorMessage } from "../../utils/errors";

const money = (v) => `₹${Number(v).toLocaleString("en-IN")}`;

function ServiceRow({ item, onChange, onRemove }) {
  const [price, setPrice] = useState(item.custom_price);
  const [busy, setBusy] = useState(false);
  const dirty = String(price) !== String(item.custom_price);

  async function save() {
    setBusy(true);
    try {
      await onChange(item.id, { custom_price: price });
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className={`row ${item.is_active ? "" : "row--off"}`}>
      <div>
        <strong>{item.service_name}</strong>
        <span className="muted"> · {item.category_name} · list price {money(item.base_price)}</span>
      </div>
      <label className="inline-field">
        Your price ₹
        <input type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} />
      </label>
      {dirty && <Button size="small" disabled={busy} onClick={save}>Save</Button>}
      <Button variant="ghost" size="small" onClick={() => onChange(item.id, { is_active: !item.is_active })}>
        {item.is_active ? "Switch off" : "Switch on"}
      </Button>
      {item.is_active && <Button variant="ghost" size="small" onClick={() => onRemove(item.id)}>Remove</Button>}
    </li>
  );
}

export default function Services() {
  const mine = useLoad(listMyServices);
  const catalogue = useLoad(() => listServices({ pageSize: 100 }).then((d) => d.results));
  const [pick, setPick] = useState({ service: "", custom_price: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const offeredIds = useMemo(() => new Set((mine.data ?? []).filter((s) => s.is_active).map((s) => s.service)), [mine.data]);
  const choices = (catalogue.data ?? []).filter((s) => !offeredIds.has(s.id));

  async function add(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const body = { service: Number(pick.service) };
      if (pick.custom_price !== "") body.custom_price = pick.custom_price;
      await offerService(body);
      mine.setData(await listMyServices());
      setPick({ service: "", custom_price: "" });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function change(id, body) {
    setError("");
    try {
      const updated = await updateMyService(id, body);
      mine.setData(mine.data.map((s) => (s.id === id ? updated : s)));
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function remove(id) {
    setError("");
    try {
      await removeMyService(id);
      mine.setData(mine.data.map((s) => (s.id === id ? { ...s, is_active: false } : s)));
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <AccountCard>
<form className="form" onSubmit={add}>
        <label>
          Add a service
          <select value={pick.service} onChange={(e) => setPick((p) => ({ ...p, service: e.target.value }))} required>
            <option value="">{catalogue.status === "loading" ? "Loading…" : "Choose a service"}</option>
            {choices.map((s) => <option key={s.id} value={s.id}>{s.name} ({money(s.base_price)})</option>)}
          </select>
        </label>
        <label>
          Your price ₹ (leave empty to use the list price)
          <input type="number" min="0" step="0.01" value={pick.custom_price} onChange={(e) => setPick((p) => ({ ...p, custom_price: e.target.value }))} />
        </label>
        <Button type="submit" disabled={busy || !pick.service}>{busy ? "Adding…" : "Add service"}</Button>
      </form>
      <ErrorMessage message={error} />

      <h2 className="section-title">What you offer</h2>
      {mine.status === "loading" && <Spinner />}
      {mine.status === "error" && <ErrorMessage message={mine.error} onRetry={mine.reload} />}
      {mine.status === "ready" && mine.data.length === 0 && <p className="empty">You have not added any service yet.</p>}
      {mine.status === "ready" && mine.data.length > 0 && (
        <ul className="rows">
          {mine.data.map((s) => <ServiceRow key={`${s.id}-${s.custom_price}`} item={s} onChange={change} onRemove={remove} />)}
        </ul>
      )}
    </AccountCard>
  );
}
