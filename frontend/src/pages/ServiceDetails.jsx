
import { useCallback, useEffect, useState } from "react";
import {
  Link,
  useLocation as useRouterLocation,
  useParams,
} from "react-router-dom";

import { listAreas, getService } from "../api/catalog";
import { listServiceProviders } from "../api/providers";

import Button from "../components/Button";
import BookingForm from "../components/BookingForm";
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

const money = (value) =>
  value === undefined || value === null || value === ""
    ? ""
    : `₹${Number(value).toLocaleString("en-IN")}`;

const duration = (minutes) => {
  if (!minutes) return "";

  const h = Math.floor(minutes / 60);
  const m = minutes % 60;

  return [h && `${h} hr`, m && `${m} min`]
    .filter(Boolean)
    .join(" ");
};

/** Local datetime value for the datetime-local input. */
const nowLocal = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};

/** A provider who can perform the selected service. */
function ProviderCard({
  offer,
  service,
  canBook,
  isPhoneVerified,
  here,
  onBook,
}) {
  const name = offer.display_name ?? `Provider#${offer.provider}`;
  const price = offer.price ?? service.base_price;

  const minutes =
    offer.estimated_duration_minutes ??
    service.estimated_duration_minutes;

  const years = offer.experience_years;

  return (
    <li className="provider-card">
      <div className="provider-card__avatar" aria-hidden="true">
        {String(name).slice(0, 1).toUpperCase()}
      </div>

      <div className="provider-card__info">
        <strong>{name}</strong>

        {offer.bio && <span>{offer.bio}</span>}

        <span>
          {[
            years ? `${years} yr experience` : "",
            minutes ? duration(minutes) : "",
            offer.is_online === false ? "Offline now" : "",
          ]
            .filter(Boolean)
            .join(" · ")}
        </span>
      </div>

      <div className="provider-card__price">
        {money(price)}
      </div>

      {canBook === "guest" && (
        <Link
          className="btn btn--primary btn--small"
          to="/login"
          state={{ from: here.pathname + here.search }}
        >
          Log in to book
        </Link>
      )}

      {canBook === "customer" &&
        (isPhoneVerified ? (
          <Button
            size="small"
            onClick={() => onBook(offer)}
          >
            Book
          </Button>
        ) : (
          <Link
            className="btn btn--primary btn--small"
            to="/verify-phone"
            state={{ from: here.pathname + here.search }}
          >
            Verify phone
          </Link>
        ))}
    </li>
  );
}

export default function ServiceDetails() {
  const { id } = useParams();
  const here = useRouterLocation();

  const { user } = useAuth();
  const { selectedCity, selectedCityId } = useLocation();

  const [service, setService] = useState({
    status: "loading",
    data: null,
    error: "",
  });

  const [areas, setAreas] = useState([]);

  const [filters, setFilters] = useState({
    area: "",
    when: "",
    ordering: "",
  });

  const [providers, setProviders] = useState({
    status: "loading",
    items: [],
    next: false,
    page: 1,
    error: "",
    more: false,
  });

  const [attempt, setAttempt] = useState(0);

  // Selected provider for the booking form.
  const [bookingProvider, setBookingProvider] = useState(null);

  // Determine the current user's booking permissions.
  const canBook = !user
    ? "guest"
    : user.role === "customer"
      ? "customer"
      : null;

  // 1. Fetch service details.
  useEffect(() => {
    let cancelled = false;

    setService({
      status: "loading",
      data: null,
      error: "",
    });

    getService(id, { city: selectedCityId })
      .then((data) => {
        if (!cancelled) {
          setService({
            status: "ready",
            data,
            error: "",
          });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setService({
            status: "error",
            data: null,
            error: getErrorMessage(error),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [id, selectedCityId, attempt]);

  // 2. Fetch areas for the selected city.
  useEffect(() => {
    let cancelled = false;

    setFilters((current) => ({
      ...current,
      area: "",
    }));

    if (!selectedCityId) {
      setAreas([]);
      return undefined;
    }

    listAreas(selectedCityId)
      .then((data) => {
        if (!cancelled) {
          setAreas(
            Array.isArray(data)
              ? data
              : data.results ?? []
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAreas([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedCityId]);

  // 3. Fetch providers whenever filters change.
  const fetchPage = useCallback(
    (page) =>
      listServiceProviders(id, {
        city: selectedCityId,
        area: filters.area,
        scheduledAt: filters.when
          ? new Date(filters.when).toISOString()
          : undefined,
        ordering: filters.ordering,
        page,
        pageSize: PAGE_SIZE,
      }),
    [id, selectedCityId, filters]
  );

  useEffect(() => {
    let cancelled = false;

    setProviders({
      status: "loading",
      items: [],
      next: false,
      page: 1,
      error: "",
      more: false,
    });

    fetchPage(1)
      .then((data) => {
        if (!cancelled) {
          setProviders({
            status: "ready",
            items: data.results,
            next: Boolean(data.next),
            page: 1,
            error: "",
            more: false,
          });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setProviders((current) => ({
            ...current,
            status: "error",
            error: getErrorMessage(error),
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [fetchPage, attempt]);

  // 4. Load the next provider page.
  async function loadMore() {
    setProviders((current) => ({
      ...current,
      more: true,
      error: "",
    }));

    try {
      const data = await fetchPage(providers.page + 1);

      setProviders((current) => ({
        ...current,
        items: [...current.items, ...data.results],
        next: Boolean(data.next),
        page: current.page + 1,
        more: false,
      }));
    } catch (error) {
      setProviders((current) => ({
        ...current,
        more: false,
        error: getErrorMessage(error),
      }));
    }
  }

  const setFilter = (field) => (event) => {
    setFilters((current) => ({
      ...current,
      [field]: event.target.value,
    }));
  };

  // 5. Handle service loading and errors.
  if (service.status === "loading") {
    return <Spinner label="Loading service…" />;
  }

  if (service.status === "error") {
    return (
      <section className="page service-details">
        <Link to="/services" className="back-link">
          ← All services
        </Link>

        <ErrorMessage
          message={service.error}
          onRetry={() => setAttempt((n) => n + 1)}
        />
      </section>
    );
  }

  const s = service.data;

  const unavailableHere =
    selectedCityId && s.available_in_city === false;

  return (
    <section
      className="page service-details"
      aria-labelledby="service-title"
    >
      <Link to="/services" className="back-link">
        ← All services
      </Link>

      {/* Service information */}
      <div className="service-hero">
        {s.image ? (
          <img
            className="service-hero__image"
            src={s.image}
            alt=""
          />
        ) : (
          <div
            className="service-hero__image icon-fallback"
            aria-hidden="true"
          >
            {s.name.slice(0, 1).toUpperCase()}
          </div>
        )}

        <div>
          <h1 id="service-title">{s.name}</h1>

          {s.category?.name && (
            <p className="muted">{s.category.name}</p>
          )}

          {s.description && <p>{s.description}</p>}

          <p className="service-hero__facts">
            {s.base_price != null && (
              <span>
                Starting at <strong>{money(s.base_price)}</strong>
              </span>
            )}

            {s.estimated_duration_minutes ? (
              <span>
                About {duration(s.estimated_duration_minutes)}
              </span>
            ) : null}
          </p>
        </div>
      </div>

      {unavailableHere && (
        <p className="alert alert--error">
          This service is not available in {selectedCity?.name} yet.
          Try another city.
        </p>
      )}

      {/* Provider filters */}
      <h2 className="section-title">Choose a provider</h2>

      <div className="filters">
        {areas.length > 0 && (
          <label>
            Area

            <select
              value={filters.area}
              onChange={setFilter("area")}
            >
              <option value="">
                All areas
                {selectedCity ? ` in ${selectedCity.name}` : ""}
              </option>

              {areas.map((area) => (
                <option key={area.id} value={area.id}>
                  {area.name}
                </option>
              ))}
            </select>
          </label>
        )}

        <label>
          Date and time

          <input
            type="datetime-local"
            min={nowLocal()}
            value={filters.when}
            onChange={setFilter("when")}
          />
        </label>

        <label>
          Sort by

          <select
            value={filters.ordering}
            onChange={setFilter("ordering")}
          >
            {SORTS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        {filters.when && (
          <Button
            variant="ghost"
            size="small"
            onClick={() =>
              setFilters((current) => ({
                ...current,
                when: "",
              }))
            }
          >
            Clear time
          </Button>
        )}
      </div>

      {!selectedCityId && (
        <p className="muted">
          Pick your location in the header to see providers near you.
        </p>
      )}

      {/* Provider results */}
      {providers.status === "loading" && (
        <Spinner label="Finding providers…" />
      )}

      {providers.status === "error" && (
        <ErrorMessage
          message={providers.error}
          onRetry={() => setAttempt((n) => n + 1)}
        />
      )}

      {providers.status === "ready" &&
        providers.error && (
          <ErrorMessage message={providers.error} />
        )}

      {providers.status === "ready" &&
        providers.items.length === 0 && (
          <p className="empty">
            {filters.when
              ? "No provider is free at that time. Try another time or area."
              : "No providers available for this service yet."}
          </p>
        )}

      {providers.items.length > 0 && (
        <ul className="provider-list">
          {providers.items.map((offer, index) => (
            <ProviderCard
              key={offer.id ?? `${offer.provider}-${index}`}
              offer={offer}
              service={s}
              canBook={canBook}
              isPhoneVerified={user?.is_phone_verified}
              here={here}
              onBook={setBookingProvider}
            />
          ))}
        </ul>
      )}

      {providers.next && (
        <Button
          className="load-more"
          variant="ghost"
          onClick={loadMore}
          disabled={providers.more}
        >
          {providers.more ? "Loading…" : "Load more"}
        </Button>
      )}

      {/* Booking form */}
      {bookingProvider && (
        <BookingForm
          service={s}
          provider={bookingProvider}
          cityId={selectedCityId}
          initialDateTime={filters.when}
          onClose={() => setBookingProvider(null)}
        />
      )}
    </section>
  );
}
