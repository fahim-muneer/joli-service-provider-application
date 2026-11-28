
import { useState } from "react";
import {
  cancelAdminBooking,
  getAdminBooking,
  listAdminBookings,
} from "../../api/admin";
import Button from "../../components/Button";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import StatusBadge from "../../components/StatusBadge";
import { useLoad } from "../../hooks";

const BOOKING_STATUS = {
  requested: { label: "Requested", tone: "info" },
  accepted: { label: "Accepted", tone: "ok" },
  in_progress: { label: "In progress", tone: "info" },
  completed: { label: "Completed", tone: "ok" },
  cancelled: { label: "Cancelled", tone: "bad" },
  expired: { label: "Expired", tone: "muted" },
};

const TABS = [
  ["", "All"],
  ["requested", "Requested"],
  ["accepted", "Accepted"],
  ["in_progress", "In progress"],
  ["completed", "Completed"],
  ["cancelled", "Cancelled"],
  ["expired", "Expired"],
];

const CANCEL_REASONS = [
  ["policy_violation", "Policy violation"],
  ["changed_mind", "Customer changed their mind"],
  ["booked_by_mistake", "Booked by mistake"],
  ["found_another_provider", "Found another provider"],
  ["schedule_conflict", "Schedule conflict"],
  ["price_too_high", "Price too high"],
  ["provider_unavailable", "Provider unavailable"],
  ["emergency", "Emergency"],
  ["customer_unreachable", "Customer unreachable"],
  ["wrong_address", "Wrong address"],
  ["other", "Other"],
];

const formatDateTime = (value) =>
  value
    ? new Date(value).toLocaleString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";

const money = (amount, currency = "INR") =>
  amount == null
    ? "—"
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
      }).format(Number(amount));

const canAdminCancel = (status) =>
  !["completed", "cancelled", "expired"].includes(status);

export default function Bookings() {
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState(null);

  const [reason, setReason] = useState("policy_violation");
  const [note, setNote] = useState("");
  const [cancelError, setCancelError] = useState("");
  const [cancelMessage, setCancelMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const list = useLoad(
    () => listAdminBookings({ status, search: query, page, pageSize: 20 }),
    [status, query, page],
  );

  const detail = useLoad(
    () => (selectedId ? getAdminBooking(selectedId) : Promise.resolve(null)),
    [selectedId],
  );

  const pickStatus = (value) => {
    setStatus(value);
    setPage(1);
  };

  const doSearch = (e) => {
    e.preventDefault();
    setQuery(search.trim());
    setPage(1);
  };

  const openBooking = (id) => {
    setSelectedId(id);
    setCancelError("");
    setCancelMessage("");
  };

  const closeBooking = () => {
    setSelectedId(null);
    setCancelError("");
    setCancelMessage("");
  };

  const handleCancel = async (e) => {
    e.preventDefault();
    if (!selectedId) return;

    setSubmitting(true);
    setCancelError("");
    setCancelMessage("");

    try {
      await cancelAdminBooking(selectedId, {
        reason_code: reason,
        note: note.trim(),
      });

      setCancelMessage("Booking cancelled successfully.");
      setNote("");
      await list.reload();
      await detail.reload();
    } catch (error) {
      setCancelError(
        error.response?.data?.detail ||
          error.response?.data?.message ||
          "Unable to cancel this booking. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const booking = detail.data;

  return (
    <>
      <div className="page-head">
        <h1>Bookings</h1>
        <p>
          {list.status === "ready"
            ? `${list.data.count} bookings`
            : "Loading bookings…"}
        </p>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={status === value}
            className={`tab ${status === value ? "tab--on" : ""}`}
            onClick={() => pickStatus(value)}
          >
            {label}
          </button>
        ))}
      </div>

      <form className="filters row" onSubmit={doSearch}>
        <label className="grow">
          Search by booking reference or customer
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Enter reference or customer name"
          />
        </label>
        <Button type="submit" size="small">
          Search
        </Button>
      </form>

      {list.status === "loading" && (
        <Spinner label="Loading bookings…" />
      )}

      {list.status === "error" && (
        <ErrorMessage message={list.error} onRetry={list.reload} />
      )}

      {list.status === "ready" && list.data.results.length === 0 && (
        <p className="empty">No bookings found.</p>
      )}

      {list.status === "ready" && list.data.results.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Reference</th>
                <th>Customer</th>
                <th>Service</th>
                <th>Scheduled date</th>
                <th>Provider</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>
              {list.data.results.map((item) => (
                <tr key={item.id}>
                  <td>{item.reference}</td>
                  <td>
                    <strong>{item.customer?.name || "—"}</strong>
                    <small className="muted" style={{ display: "block" }}>
                      {item.customer?.phone || ""}
                    </small>
                  </td>
                  <td>{item.service?.name || "—"}</td>
                  <td>{formatDateTime(item.scheduled_at)}</td>
                  <td>{item.provider?.display_name || "Not assigned"}</td>
                  <td>{money(item.estimated_total, item.currency)}</td>
                  <td>
                    <StatusBadge
                      table={BOOKING_STATUS}
                      value={item.status}
                    />
                  </td>
                  <td>
                    <Button
                      variant="ghost"
                      size="small"
                      onClick={() => openBooking(item.id)}
                    >
                      View
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {list.status === "ready" &&
        (list.data.previous || list.data.next) && (
          <div className="pager">
            <Button
              variant="ghost"
              size="small"
              disabled={!list.data.previous}
              onClick={() => setPage((n) => n - 1)}
            >
              Previous
            </Button>

            <span>
              Page {page} · {list.data.count} bookings
            </span>

            <Button
              variant="ghost"
              size="small"
              disabled={!list.data.next}
              onClick={() => setPage((n) => n + 1)}
            >
              Next
            </Button>
          </div>
        )}

      {selectedId && (
        <section className="table-wrap" style={{ marginTop: 24, padding: 20 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>Booking details</h2>
            <Button variant="ghost" size="small" onClick={closeBooking}>
              Close
            </Button>
          </div>

          {detail.status === "loading" && (
            <Spinner label="Loading booking details…" />
          )}

          {detail.status === "error" && (
            <ErrorMessage message={detail.error} onRetry={detail.reload} />
          )}

          {detail.status === "ready" && booking && (
            <>
              <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
                <strong>{booking.reference}</strong>
                <StatusBadge
                  table={BOOKING_STATUS}
                  value={booking.status}
                />
              </div>

              <div className="table-wrap" style={{ marginTop: 16 }}>
                <table className="table">
                  <tbody>
                    <tr>
                      <th>Customer</th>
                      <td>{booking.customer?.name || "—"}</td>
                    </tr>
                    <tr>
                      <th>Phone</th>
                      <td>{booking.customer?.phone || "—"}</td>
                    </tr>
                    <tr>
                      <th>Service</th>
                      <td>{booking.service?.name || "—"}</td>
                    </tr>
                    <tr>
                      <th>Provider</th>
                      <td>{booking.provider?.display_name || "Not assigned"}</td>
                    </tr>
                    <tr>
                      <th>Scheduled at</th>
                      <td>{formatDateTime(booking.scheduled_at)}</td>
                    </tr>
                    <tr>
                      <th>Duration</th>
                      <td>{booking.duration_minutes} minutes</td>
                    </tr>
                    <tr>
                      <th>Payment mode</th>
                      <td>{booking.payment_mode || "—"}</td>
                    </tr>
                    <tr>
                      <th>Estimated total</th>
                      <td>{money(booking.estimated_total, booking.currency)}</td>
                    </tr>
                    <tr>
                      <th>Customer notes</th>
                      <td>{booking.customer_notes || "—"}</td>
                    </tr>
                    <tr>
                      <th>Created</th>
                      <td>{formatDateTime(booking.created_at)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <h3 style={{ marginTop: 20 }}>Provider offers</h3>
              {booking.offers?.length > 0 ? (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Provider ID</th>
                        <th>Status</th>
                        <th>Offered at</th>
                        <th>Responded at</th>
                        <th>Decline reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {booking.offers.map((offer, index) => (
                        <tr key={`${offer.provider}-${index}`}>
                          <td>{offer.provider}</td>
                          <td>{offer.status}</td>
                          <td>{formatDateTime(offer.offered_at)}</td>
                          <td>{formatDateTime(offer.responded_at)}</td>
                          <td>{offer.decline_reason || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">No provider offers available.</p>
              )}

              <h3 style={{ marginTop: 20 }}>Status history</h3>
              {booking.status_history?.length > 0 ? (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Status</th>
                        <th>Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {booking.status_history.map((entry, index) => (
                        <tr key={entry.id || index}>
                          <td>{entry.status}</td>
                          <td>{formatDateTime(entry.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">No status history available.</p>
              )}

              {cancelMessage && (
                <p role="status">{cancelMessage}</p>
              )}

              {cancelError && (
                <ErrorMessage message={cancelError} />
              )}

              {canAdminCancel(booking.status) && (
                <form
                  className="filters"
                  style={{ marginTop: 24 }}
                  onSubmit={handleCancel}
                >
                  <h3>Cancel booking</h3>

                  <label>
                    Cancellation reason
                    <select
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    >
                      {CANCEL_REASONS.map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Additional note
                    <textarea
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      maxLength={500}
                      rows={3}
                      placeholder="Enter an optional explanation"
                    />
                  </label>

                  <Button type="submit" disabled={submitting}>
                    {submitting ? "Cancelling…" : "Cancel booking"}
                  </Button>
                </form>
              )}
            </>
          )}
        </section>
      )}
    </>
  );
}
