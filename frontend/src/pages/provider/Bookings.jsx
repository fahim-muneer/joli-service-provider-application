import { useCallback, useEffect, useState } from "react";
import {
  cancelProviderBooking,
  completeProviderBooking,
  getCancelReasons,
  listProviderBookings,
  startProviderBooking,
} from "../../api/bookings";
import Button from "../../components/Button";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import { getErrorMessage } from "../../utils/errors";
import "../../styles/provider-bookings.css";

function formatDate(value) {
  if (!value) return "Not available";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatMoney(value, currency = "INR") {
  if (value === null || value === undefined) return "Not available";

  const amount = Number(value);
  if (!Number.isFinite(amount)) return "Not available";

  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

function statusLabel(status) {
  return (
    {
      requested: "Requested",
      accepted: "Accepted",
      in_progress: "In progress",
      completed: "Completed",
      cancelled: "Cancelled",
      expired: "Expired",
    }[status] || status || "Unknown"
  );
}

function getServiceName(service) {
  if (typeof service === "string") return service;
  return service?.name || service?.title || "Service booking";
}

function getCustomerName(customer) {
  if (typeof customer === "string") return customer;

  return (
    customer?.display_name ||
    customer?.full_name ||
    customer?.name ||
    "Customer"
  );
}

function getCustomerPhone(customer) {
  if (typeof customer === "object" && customer) {
    return customer.phone || customer.mobile_number || "";
  }
  return "";
}

function addressLines(value) {
  if (!value) return [];

  if (typeof value !== "object") {
    return [String(value)];
  }

  if (Array.isArray(value)) {
    return value.flatMap(addressLines);
  }

  return Object.entries(value)
    .filter(([, item]) => item !== null && item !== undefined && item !== "")
    .filter(([key]) =>
      !["id", "latitude", "longitude", "lat", "lng"].includes(key)
    )
    .flatMap(([, item]) =>
      typeof item === "object" ? addressLines(item) : [String(item)]
    )
    .filter(Boolean);
}

function BookingCard({
  booking,
  reasons,
  busy,
  startCode,
  completionNote,
  cancelForm,
  onStartCodeChange,
  onCompletionNoteChange,
  onCancelFormChange,
  onStart,
  onComplete,
  onCancel,
}) {
  const customer = booking.customer;
  const address = addressLines(booking.address);

  return (
    <article className="provider-booking">
      <div className="provider-booking__header">
        <div>
          <p className="provider-booking__reference">
            Reference: {booking.reference || booking.id}
          </p>
          <h2>{getServiceName(booking.service)}</h2>
          <p className="provider-booking__customer">
            Customer: <strong>{getCustomerName(customer)}</strong>
            {getCustomerPhone(customer) && (
              <> · {getCustomerPhone(customer)}</>
            )}
          </p>
        </div>

        <span
          className={`booking-status booking-status--${booking.status}`}
        >
          {statusLabel(booking.status)}
        </span>
      </div>

      <div className="provider-booking__facts">
        <div>
          <span>Scheduled date</span>
          <strong>{formatDate(booking.scheduled_at)}</strong>
        </div>
        <div>
          <span>Expected end</span>
          <strong>{formatDate(booking.ends_at)}</strong>
        </div>
        <div>
          <span>Duration</span>
          <strong>
            {booking.duration_minutes
              ? `${booking.duration_minutes} minutes`
              : "Not available"}
          </strong>
        </div>
        <div>
          <span>Items</span>
          <strong>{booking.item_count ?? "Not available"}</strong>
        </div>
        <div>
          <span>Estimated amount</span>
          <strong>
            {formatMoney(booking.estimated_total, booking.currency)}
          </strong>
        </div>
        <div>
          <span>Payment method</span>
          <strong>
            {booking.payment_mode === "cash"
              ? "Cash"
              : booking.payment_mode === "online"
                ? "Online"
                : booking.payment_mode || "Not available"}
          </strong>
        </div>
      </div>

      <div className="provider-booking__section">
        <h3>Service address</h3>
        {address.length ? (
          <p>{address.join(", ")}</p>
        ) : (
          <p className="provider-booking__muted">
            Address information is not available.
          </p>
        )}
      </div>

      {booking.customer_notes && (
        <div className="provider-booking__section">
          <h3>Customer notes</h3>
          <p>{booking.customer_notes}</p>
        </div>
      )}

      {booking.status === "accepted" && (
        <div className="provider-booking__action">
          <h3>Start this service</h3>

          {booking.can_start ? (
            <>
              <p>Ask the customer for their six-digit service start code.</p>
              <form
                className="provider-booking__action-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  onStart(booking.id);
                }}
              >
                <label>
                  Customer's six-digit code
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    pattern="[0-9]{6}"
                    value={startCode}
                    onChange={(event) =>
                      onStartCodeChange(booking.id, event.target.value.replace(/\D/g, "").slice(0, 6))
                    }
                    placeholder="Enter 6-digit code"
                    required
                    disabled={busy}
                  />
                </label>
                <Button type="submit" disabled={busy || startCode.length !== 6}>
                {busy ? "Starting…" : "Start service"}
                </Button>
              </form>
            </>
          ) : (
            <p className="provider-booking__muted">
              The service cannot be started yet.
              {booking.start_opens_at
                ? ` Start is available from ${formatDate(booking.start_opens_at)}.`
                : " Please check the scheduled time."}
            </p>
          )}
        </div>
      )}

      {booking.status === "in_progress" && (
        <div className="provider-booking__action">
          <h3>Complete this service</h3>
          <label>
            Completion note (optional)
            <textarea
              rows={2}
              maxLength={500}
              value={completionNote}
              onChange={(event) =>
                onCompletionNoteChange(booking.id, event.target.value)
              }
              placeholder="Add a short completion note"
              disabled={busy}
            />
          </label>
          <Button disabled={busy} onClick={() => onComplete(booking.id)}>
            {busy ? "Completing…" : "Mark as completed"}
          </Button>
        </div>
      )}

      {booking.can_cancel && (
        <div className="provider-booking__action provider-booking__cancel">
          <h3>Cancel accepted booking</h3>
          <form
            className="provider-booking__cancel-form"
            onSubmit={(event) => {
              event.preventDefault();
              onCancel(booking.id);
            }}
          >
            <label>
              Cancellation reason
              <select
                value={cancelForm.reason_code}
                onChange={(event) =>
                  onCancelFormChange(booking.id, {
                    ...cancelForm,
                    reason_code: event.target.value,
                  })
                }
                required
                disabled={busy}
              >
                <option value="">Select a reason</option>
                {reasons.map((reason) => (
                  <option key={reason.code} value={reason.code}>
                    {reason.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Additional note (optional)
              <textarea
                rows={2}
                maxLength={500}
                value={cancelForm.note}
                onChange={(event) =>
                  onCancelFormChange(booking.id, {
                    ...cancelForm,
                    note: event.target.value,
                  })
                }
                placeholder="Explain the reason, if needed"
                disabled={busy}
              />
            </label>

            <Button type="submit" disabled={busy || !cancelForm.reason_code}>
            {busy ? "Cancelling…" : "Confirm cancellation"}
            </Button>
          </form>
        </div>
      )}
    </article>
  );
}

export default function ProviderBookings() {
  const [scope, setScope] = useState("upcoming");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [bookings, setBookings] = useState([]);
  const [pagination, setPagination] = useState({
    next: null,
    previous: null,
    count: 0,
  });
  const [reasons, setReasons] = useState([]);
  const [startCodes, setStartCodes] = useState({});
  const [completionNotes, setCompletionNotes] = useState({});
  const [cancelForms, setCancelForms] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const loadBookings = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const params = { scope, page };
      if (status) params.status = status;

      const [bookingData, reasonData] = await Promise.all([
        listProviderBookings(params),
        getCancelReasons(),
      ]);

      const results = Array.isArray(bookingData)
        ? bookingData
        : bookingData?.results || [];

      setBookings(results);
      setPagination({
        next: bookingData?.next || null,
        previous: bookingData?.previous || null,
        count: bookingData?.count ?? results.length,
      });
      setReasons(reasonData?.provider || []);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [scope, status, page, reloadKey]);

  useEffect(() => {
    loadBookings();
  }, [loadBookings]);

  function updateById(setter, id, value) {
    setter((current) => ({ ...current, [id]: value }));
  }

  async function runAction(id, action) {
    setBusyId(id);
    setActionError("");

    try {
      await action();
      setStartCodes((current) => ({ ...current, [id]: "" }));
      setCompletionNotes((current) => ({ ...current, [id]: "" }));
      setCancelForms((current) => ({ ...current, [id]: { reason_code: "", note: "" } }));
      setReloadKey((current) => current + 1);
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  function handleStart(id) {
    const code = startCodes[id] || "";

    if (!/^\d{6}$/.test(code)) {
      setActionError("Enter the six-digit code provided by the customer.");
      return;
    }

    runAction(id, () => startProviderBooking(id, code));
  }

  function handleComplete(id) {
    runAction(id, () =>
      completeProviderBooking(id, completionNotes[id] || "")
    );
  }

  function handleCancel(id) {
    const form = cancelForms[id] || { reason_code: "", note: "" };

    if (!form.reason_code) {
      setActionError("Please select a cancellation reason.");
      return;
    }

    if (!window.confirm("Are you sure you want to cancel this booking?")) {
      return;
    }

    runAction(id, () =>
      cancelProviderBooking(id, {
        reason_code: form.reason_code,
        note: form.note.trim(),
      })
    );
  }

  function changeScope(nextScope) {
    setScope(nextScope);
    setPage(1);
    setStatus("");
  }

  function changeStatus(nextStatus) {
    setStatus(nextStatus);
    setPage(1);
  }

  if (loading && bookings.length === 0 && !error) {
    return <Spinner label="Loading your bookings…" />;
  }

  return (
    <section className="provider-bookings-page">
      <div className="provider-bookings-page__heading">
        <div>
          <p className="bookings-page__eyebrow">PROVIDER PORTAL</p>
          <h2>My Bookings</h2>
          <p>Manage the service bookings you have accepted.</p>
        </div>

        <Button
          disabled={loading || busyId !== null}
          onClick={() => setReloadKey((current) => current + 1)}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </Button>
      </div>

      <div className="provider-bookings-toolbar">
        <div className="provider-bookings-tabs">
          <button
            type="button"
            className={scope === "upcoming" ? "is-active" : ""}
            onClick={() => changeScope("upcoming")}
          >
            Upcoming
          </button>
          <button
            type="button"
            className={scope === "history" ? "is-active" : ""}
            onClick={() => changeScope("history")}
          >
            History
          </button>
        </div>

        <label className="provider-bookings-filter">
          Status
          <select
            value={status}
            onChange={(event) => changeStatus(event.target.value)}
          >
            <option value="">All statuses</option>
            <option value="accepted">Accepted</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </label>
      </div>

      <ErrorMessage message={error || actionError} />

      {loading && bookings.length > 0 && (
        <Spinner label="Refreshing bookings…" />
      )}

      {!loading && bookings.length === 0 && !error && (
        <div className="provider-bookings-empty">
          <h3>No bookings found</h3>
          <p>
            {scope === "upcoming"
              ? "Bookings you accept will appear here."
              : "Your completed and past bookings will appear here."}
          </p>
        </div>
      )}

      <div className="provider-bookings-list">
        {bookings.map((booking) => (
          <BookingCard
            key={booking.id}
            booking={booking}
            reasons={reasons}
            busy={busyId === booking.id}
            startCode={startCodes[booking.id] || ""}
            completionNote={completionNotes[booking.id] || ""}
            cancelForm={
              cancelForms[booking.id] || { reason_code: "", note: "" }
            }
            onStartCodeChange={(id, value) =>
              updateById(setStartCodes, id, value)
            }
            onCompletionNoteChange={(id, value) =>
              updateById(setCompletionNotes, id, value)
            }
            onCancelFormChange={(id, value) =>
              updateById(setCancelForms, id, value)
            }
            onStart={handleStart}
            onComplete={handleComplete}
            onCancel={handleCancel}
          />
        ))}
      </div>

      {(pagination.previous || pagination.next) && (
        <div className="provider-bookings-pagination">
          <Button
            disabled={!pagination.previous || loading}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            Previous
          </Button>
          <span>{pagination.count} booking(s)</span>
          <Button
            disabled={!pagination.next || loading}
            onClick={() => setPage((current) => current + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </section>
  );
}