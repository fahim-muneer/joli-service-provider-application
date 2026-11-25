
import { useState } from "react";
import { listAreas, listCities } from "../../api/catalog";
import { listMyAreas, replaceMyAreas } from "../../api/provider";
import Button from "../../components/Button";
import AccountCard from "../../components/portal/AccountCard";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import { useLoad } from "../../hooks";
import { getErrorMessage } from "../../utils/errors";

const asList = (data) =>
  Array.isArray(data) ? data : data?.results ?? [];

export default function Areas() {
  const mine = useLoad(listMyAreas);
  const cities = useLoad(() => listCities().then(asList));

  const [selectedOverride, setSelectedOverride] = useState(null);
  const [cityId, setCityId] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const areasRequest = useLoad(
    () => (cityId ? listAreas(cityId).then(asList) : Promise.resolve([])),
    [cityId]
  );

  // Use saved provider areas initially.
  // After the user changes selections, use their updated selection.
  const selected =
    selectedOverride ??
    new Set((mine.data ?? []).map((area) => area.id));

  function toggle(id) {
    setSaved(false);
    setSelectedOverride((current) => {
      const next = new Set(
        current ?? (mine.data ?? []).map((area) => area.id)
      );

      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }

      return next;
    });
  }

  async function save() {
    setError("");
    setBusy(true);

    try {
      const updated = await replaceMyAreas([...selected]);

      mine.setData(updated);
      setSelectedOverride(null);
      setSaved(true);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (mine.status === "loading") {
    return <Spinner />;
  }

  if (mine.status === "error") {
    return (
      <section className="panel">
        <ErrorMessage
          message={mine.error}
          onRetry={mine.reload}
        />
      </section>
    );
  }

  const names = new Map(
    (mine.data ?? []).map((area) => [
      area.id,
      `${area.name}, ${area.city_name}`,
    ])
  );

  const areas = areasRequest.data ?? [];

  return (
    <AccountCard>
      <p className="muted">
        Customers in these areas can find you. {selected.size} selected.
      </p>

      <div className="form">
        <label>
          City
          <select
            value={cityId}
            onChange={(e) => setCityId(e.target.value)}
          >
            <option value="">Choose a city to pick areas</option>

            {(cities.data ?? []).map((city) => (
              <option key={city.id} value={city.id}>
                {city.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {areasRequest.status === "loading" && cityId && <Spinner />}

      {areasRequest.status === "error" && (
        <ErrorMessage
          message={areasRequest.error}
          onRetry={areasRequest.reload}
        />
      )}

      {areas.length > 0 && (
        <ul className="checks">
          {areas.map((area) => (
            <li key={area.id}>
              <label>
                <input
                  type="checkbox"
                  checked={selected.has(area.id)}
                  onChange={() => toggle(area.id)}
                />
                {area.name}{" "}
                {area.pincode && (
                  <span className="muted">{area.pincode}</span>
                )}
              </label>
            </li>
          ))}
        </ul>
      )}

      {selected.size > 0 && (
        <p className="muted">
          Currently covered:{" "}
          {[...selected]
            .map((id) => names.get(id) ?? `area ${id}`)
            .join(" · ")}
        </p>
      )}

      {saved && (
        <p className="notice" role="status">
          Saved.
        </p>
      )}

      <ErrorMessage message={error} />

      <Button disabled={busy} onClick={save}>
        {busy ? "Saving…" : "Save areas"}
      </Button>
    </AccountCard>
  );
}
