import { useEffect, useState } from "react";
import { listAreas, listCities } from "../../api/catalog";
import { listMyAreas, replaceMyAreas } from "../../api/provider";
import Button from "../../components/Button";
import AccountCard from "../../components/portal/AccountCard";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import { useLoad } from "../../hooks";
import { getErrorMessage } from "../../utils/errors";

const asList = (data) => (Array.isArray(data) ? data : data?.results ?? []);

export default function Areas() {
  const mine = useLoad(listMyAreas);
  const cities = useLoad(() => listCities().then(asList));
  const [selected, setSelected] = useState(() => new Set()); // area ids, across ALL cities
  const [cityId, setCityId] = useState("");
  const [areas, setAreas] = useState([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (mine.data) setSelected(new Set(mine.data.map((a) => a.id)));
  }, [mine.data]);

  useEffect(() => {
    if (!cityId) {
      setAreas([]);
      return undefined;
    }
    let cancelled = false;
    listAreas(cityId).then((d) => !cancelled && setAreas(asList(d))).catch((e) => !cancelled && setError(getErrorMessage(e)));
    return () => { cancelled = true; };
  }, [cityId]);

  function toggle(id) {
    setSaved(false);
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function save() {
    setError("");
    setBusy(true);
    try {
      mine.setData(await replaceMyAreas([...selected]));
      setSaved(true);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (mine.status === "loading") return <Spinner />;
  if (mine.status === "error") return <section className="panel"><ErrorMessage message={mine.error} onRetry={mine.reload} /></section>;

  const names = new Map(mine.data.map((a) => [a.id, `${a.name}, ${a.city_name}`]));

  return (
    <AccountCard>
<p className="muted">Customers in these areas can find you. {selected.size} selected.</p>

      <div className="form">
        <label>
          City
          <select value={cityId} onChange={(e) => setCityId(e.target.value)}>
            <option value="">Choose a city to pick areas</option>
            {(cities.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
      </div>

      {areas.length > 0 && (
        <ul className="checks">
          {areas.map((a) => (
            <li key={a.id}>
              <label><input type="checkbox" checked={selected.has(a.id)} onChange={() => toggle(a.id)} /> {a.name} {a.pincode && <span className="muted">{a.pincode}</span>}</label>
            </li>
          ))}
        </ul>
      )}

      {selected.size > 0 && (
        <p className="muted">Currently covered: {[...selected].map((id) => names.get(id) ?? `area ${id}`).join(" · ")}</p>
      )}
      {saved && <p className="notice" role="status">Saved.</p>}
      <ErrorMessage message={error} />
      <Button disabled={busy} onClick={save}>{busy ? "Saving…" : "Save areas"}</Button>
    </AccountCard>
  );
}
