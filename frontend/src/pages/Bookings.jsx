import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listBookings } from "../api/bookings";
import Spinner from "../components/Spinner";
import "../styles/bookings.css";

const STATUS_OPTIONS = {
  upcoming: [
    { value: "requested", label: "Requested" },
    { value: "accepted", label: "Accepted" },
    { value: "in_progress", label: "In progress" },
  ],
  history: [
    { value: "completed", label: "Completed" },
    { value: "cancelled", label: "Cancelled" },
    { value: "expired", label: "Expired" },
  ],
};

function statusLabel(status) {
  return (
    {
      requested: "Requested",
      accepted: "Accepted",
      in_progress: "In progress",
      completed: "Completed",
      cancelled: "Cancelled",
      expired: "Expired",
    }[status] || status
  );
}

function formatDate(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";

  return date.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatMoney(amount, currency = "INR") {
  if (amount === null || amount === undefined) return "Not available";

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number(amount));
}

function getErrorMessage(error) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    "Unable to load your bookings. Please try again."
  );
}

export default function Bookings() {
  const [scope, setScope] = useState("upcoming");
  const [status, setStatus] = useState("");
  const [bookings, setBookings] = useState([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;

    async function loadBookings() {
      setLoading(true);
      setError("");
      setBookings([]);
      setPage(1);

      try {
        const response = await listBookings({
          scope,
          ...(status ? { status } : {}),
          page: 1,
        });

        if (!active) return;

        const results = Array.isArray(response)
          ? response
          : response?.results || [];

        setBookings(results);
        setHasMore(Boolean(response?.next));
      } catch (err) {
        if (active) setError(getErrorMessage(err));
      } finally {
        if (active) setLoading(false);
      }
    }

    loadBookings();

    return () => {
      active = false;
    };
  }, [scope, status, reloadKey]);

  async function loadMore() {
    const nextPage = page + 1;

    setLoadingMore(true);
    setError("");

    try {
      const response = await listBookings({
        scope,
        ...(status ? { status } : {}),
        page: nextPage,
      });

      const results = Array.isArray(response)
        ? response
        : response?.results || [];

      setBookings((current) => [...current, ...results]);
      setPage(nextPage);
      setHasMore(Boolean(response?.next));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoadingMore(false);
    }
  }

  function changeScope(nextScope) {
    setScope(nextScope);
    setStatus("");
  }

  return (
    <section className="page bookings-page">
      <div className="bookings-page__heading">
        <div>
          <p className="bookings-page__eyebrow">CUSTOMER PORTAL</p>
          <h1>My Bookings</h1>
          <p className="muted">
            View your service requests and booking history.
          </p>
        </div>
        <Link to="/services" className="btn btn--primary">
          Book a service
        </Link>
      </div>

      <div className="bookings-toolbar">
        <div className="bookings-tabs" role="tablist" aria-label="Booking type">
          <button
            type="button"
            role="tab"
            aria-selected={scope === "upcoming"}
            className={scope === "upcoming" ? "is-active" : ""}
            onClick={() => changeScope("upcoming")}
          >
            Upcoming
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={scope === "history"}
            className={scope === "history" ? "is-active" : ""}
            onClick={() => changeScope("history")}
          >
            History
          </button>
        </div>

        <label className="bookings-filter">
          <span>Filter by status</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS[scope].map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading && <Spinner label="Loading your bookings..." />}

      {!loading && error && (
        <div className="bookings-message bookings-message--error" role="alert">
          <span>{error}</span>
          <button
            type="button"
            className="btn btn--ghost btn--small"
            onClick={() => setReloadKey((value) => value + 1)}
          >
            Try again
          </button>
        </div>
      )}

      {!loading && !error && bookings.length === 0 && (
        <div className="bookings-empty">
          <h2>No bookings found</h2>
          <p>
            {scope === "upcoming"
              ? "You don't have any upcoming bookings yet."
              : "Your completed and cancelled bookings will appear here."}
          </p>
          <Link to="/services" className="btn btn--primary">
            Explore services
          </Link>
        </div>
      )}

      {!loading && bookings.length > 0 && (
        <>
          <div className="booking-list">
            {bookings.map((booking) => (
              <article className="booking-card" key={booking.id}>
                <div className="booking-card__main">
                  <div className="booking-card__top">
                    <div>
                      <p className="booking-card__reference">
                        Booking #{booking.reference || booking.id}
                      </p>
                      <h2>
                        {booking.service?.name ||
                          booking.service_name ||
                          "Service booking"}
                      </h2>
                    </div>
                    <span
                      className={`booking-status booking-status--${booking.status}`}
                    >
                      {statusLabel(booking.status)}
                    </span>
                  </div>

                  <div className="booking-card__facts">
                    <div>
                      <span>Scheduled for</span>
                      <strong>{formatDate(booking.scheduled_at)}</strong>
                    </div>
                    <div>
                      <span>Provider</span>
                      <strong>
                        {booking.provider?.display_name || "Not assigned yet"}
                      </strong>
                    </div>
                    <div>
                      <span>Estimated total</span>
                      <strong>
                        {formatMoney(booking.estimated_total, booking.currency)}
                      </strong>
                    </div>
                  </div>
                </div>

                <div className="booking-card__footer">
                  {booking.can_cancel ? (
                    <span className="muted">Cancellation available</span>
                  ) : (
                    <span />
                  )}
                  <Link
                    to={`/bookings/${booking.id}`}
                    className="btn btn--ghost btn--small"
                  >
                    View details
                  </Link>
                </div>
              </article>
            ))}
          </div>

          {hasMore && (
            <div className="bookings-load-more">
              <button
                type="button"
                className="btn btn--ghost"
                disabled={loadingMore}
                onClick={loadMore}
              >
                {loadingMore ? "Loading..." : "Load more"}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}