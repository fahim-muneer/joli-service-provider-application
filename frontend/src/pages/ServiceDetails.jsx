import { useCallback, useEffect, useState } from "react";
import { Link, useLocation as useRouterLocation, useParams } from "react-router-dom";
import { listAreas, getService } from "../api/catalog";
import { listServiceProviders } from "../api/providers";
import Button from "../components/Button";
import ErrorMessage from "../components/ErrorMessage";
import Spinner from "../components/Spinner";
import { useAuth } from "../context/useAuth";
import { useLocation } from "../context/useLocation";
import { getErrorMessage } from "../utils/errors";

const PAGE_SIZE = 10;
const SORTS = [
  ["", "Recommended"],
  ["price", "Price: low to high"],
  ["-price", "Price: high to low"],
  ["-experience", "Most experienced"],
];

const money = (value) => (value === undefined || value === null || value === "" ? "" : `₹${Number(value).toLocaleString("en-IN")}`);
const duration = (minutes) => {
  if (!minutes) return "";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return [h && `${h} hr`, m && `${m} min`].filter(Boolean).join(" ");
};
/** A <input type="datetime-local"> value for "now", so past times cannot be picked (the API rejects them). */
const nowLocal = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};

/** One provider who can do this service (fields of PublicProviderOfferSerializer). */
function ProviderCard({ offer, service, canBook, here }) {
  const name = offer.display_name ?? `Provider #${offer.provider}`;
  const price = offer.price ?? service.base_price;
  const minutes = offer.estimated_duration_minutes ?? service.estimated_duration_minutes;
  const years = offer.experience_years;
  return (
    <li className="provider-card">
      <div className="provider-card__avatar" aria-hidden="true">{String(name).slice(0, 1).toUpperCase()}</div>
      <div className="provider-card__info">
        <strong>{name}</strong>
        {offer.bio && <span>{offer.bio}</span>}
        <span>
          {[years ? `${years} yr experience` : "", minutes ? duration(minutes) : "", offer.is_online === false ? "Offline now" : ""]
            .filter(Boolean)
            .join(" · ")}
        </span>
      </div>
      <div className="provider-card__price">{money(price)}</div>
      {canBook === "guest" ? (
        <Link className="btn btn--primary btn--small" to="/login" state={{ from: here.pathname + here.search }}>Log in to book</Link>
      ) : canBook === "customer" ? (
        <Button size="small" disabled title="Booking arrives with the bookings feature">Book</Button>
      ) : null}
    </li>
  );
}

export default function ServiceDetails() {
  const { id } = useParams();
  const here = useRouterLocation();
  const { user } = useAuth();
  const { selectedCity, selectedCityId } = useLocation();

  const [service, setService] = useState({ status: "loading", data: null, error: "" });
  const [areas, setAreas] = useState([]);
  const [filters, setFilters] = useState({ area: "", when: "", ordering: "" });
  const [providers, setProviders] = useState({ status: "loading", items: [], next: false, page: 1, error: "", more: false });
  const [attempt, setAttempt] = useState(0); // bump to reload after an error

  // 1. The service itself (re-fetched when the city changes: it says if the service is available there).
  useEffect(() => {
    let cancelled = false;
    setService({ status: "loading", data: null, error: "" });
    getService(id, { city: selectedCityId })
      .then((data) => !cancelled && setService({ status: "ready", data, error: "" }))
      .catch((e) => !cancelled && setService({ status: "error", data: null, error: getErrorMessage(e) }));
    return () => {
      cancelled = true;
    };
  }, [id, selectedCityId, attempt]);

  // 2. Areas of the chosen city, for the area filter.
  useEffect(() => {
    let cancelled = false;
    setFilters((f) => ({ ...f, area: "" }));
    if (!selectedCityId) {
      setAreas([]);
      return undefined;
    }
    listAreas(selectedCityId)
      .then((data) => !cancelled && setAreas(Array.isArray(data) ? data : data.results ?? []))
      .catch(() => !cancelled && setAreas([]));
    return () => {
      cancelled = true;
    };
  }, [selectedCityId]);

  // 3. Providers, whenever a filter changes.
  const fetchPage = useCallback(
    (page) =>
      listServiceProviders(id, {
        city: selectedCityId,
        area: filters.area,
        scheduledAt: filters.when ? new Date(filters.when).toISOString() : undefined,
        ordering: filters.ordering,
        page,
        pageSize: PAGE_SIZE,
      }),
    [id, selectedCityId, filters],
  );

  useEffect(() => {
    let cancelled = false;
    setProviders({ status: "loading", items: [], next: false, page: 1, error: "", more: false });
    fetchPage(1)
      .then((d) => !cancelled && setProviders({ status: "ready", items: d.results, next: Boolean(d.next), page: 1, error: "", more: false }))
      .catch((e) => !cancelled && setProviders((s) => ({ ...s, status: "error", error: getErrorMessage(e) })));
    return () => {
      cancelled = true;
    };
  }, [fetchPage, attempt]);

  async function loadMore() {
    setProviders((s) => ({ ...s, more: true }));
    try {
      const d = await fetchPage(providers.page + 1);
      setProviders((s) => ({ ...s, items: [...s.items, ...d.results], next: Boolean(d.next), page: s.page + 1, more: false }));
    } catch (e) {
      setProviders((s) => ({ ...s, more: false, error: getErrorMessage(e) }));
    }
  }

  const setFilter = (field) => (e) => setFilters((f) => ({ ...f, [field]: e.target.value }));
  const canBook = !user ? "guest" : user.role === "customer" ? "customer" : null;

  if (service.status === "loading") return <Spinner label="Loading service…" />;
  if (service.status === "error") {
    return (
      <section className="page service-details">
        <Link to="/services" className="back-link">← All services</Link>
        <ErrorMessage message={service.error} onRetry={() => setAttempt((n) => n + 1)} />
      </section>
    );
  }

  const s = service.data;
  const unavailableHere = selectedCityId && s.available_in_city === false;

  return (
    <section className="page service-details" aria-labelledby="service-title">
      <Link to="/services" className="back-link">← All services</Link>

      <div className="service-hero">
        {s.image ? <img className="service-hero__image" src={s.image} alt="" /> : <div className="service-hero__image icon-fallback" aria-hidden="true">{s.name.slice(0, 1).toUpperCase()}</div>}
        <div>
          <h1 id="service-title">{s.name}</h1>
          {s.category?.name && <p className="muted">{s.category.name}</p>}
          {s.description && <p>{s.description}</p>}
          <p className="service-hero__facts">
            {s.base_price != null && <span>Starting at <strong>{money(s.base_price)}</strong></span>}
            {s.estimated_duration_minutes ? <span>About {duration(s.estimated_duration_minutes)}</span> : null}
          </p>
        </div>
      </div>

      {unavailableHere && <p className="alert alert--error">This service is not available in {selectedCity?.name} yet. Try another city.</p>}

      <h2 className="section-title">Choose a provider</h2>
      <div className="filters">
        {areas.length > 0 && (
          <label>
            Area
            <select value={filters.area} onChange={setFilter("area")}>
              <option value="">All areas{selectedCity ? ` in ${selectedCity.name}` : ""}</option>
              {areas.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </label>
        )}
        <label>
          Date and time
          <input type="datetime-local" min={nowLocal()} value={filters.when} onChange={setFilter("when")} />
        </label>
        <label>
          Sort by
          <select value={filters.ordering} onChange={setFilter("ordering")}>
            {SORTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        {filters.when && <Button variant="ghost" size="small" onClick={() => setFilters((f) => ({ ...f, when: "" }))}>Clear time</Button>}
      </div>
      {!selectedCityId && <p className="muted">Pick your location in the header to see providers near you.</p>}

      {providers.status === "loading" && <Spinner label="Finding providers…" />}
      {providers.status === "error" && <ErrorMessage message={providers.error} onRetry={() => setAttempt((n) => n + 1)} />}
      {providers.status === "ready" && providers.error && <ErrorMessage message={providers.error} />}
      {providers.status === "ready" && providers.items.length === 0 && (
        <p className="empty">{filters.when ? "No provider is free at that time. Try another time or area." : "No providers available for this service yet."}</p>
      )}
      {providers.items.length > 0 && (
        <ul className="provider-list">
          {providers.items.map((offer, i) => (
            <ProviderCard key={offer.id ?? `${offer.provider}-${i}`} offer={offer} service={s} canBook={canBook} here={here} />
          ))}
        </ul>
      )}
      {providers.next && (
        <Button className="load-more" variant="ghost" onClick={loadMore} disabled={providers.more}>
          {providers.more ? "Loading…" : "Load more"}
        </Button>
      )}
    </section>
  );
}
