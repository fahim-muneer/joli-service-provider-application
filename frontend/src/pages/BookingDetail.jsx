import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import "../styles/bookings.css";
import {
  cancelBooking,
  getBooking,
  getCancelReasons,
} from "../api/bookings";
import Spinner from "../components/Spinner";

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

function errorMessage(error) {
  const data = error?.response?.data;

  if (typeof data?.detail === "string") return data.detail;
  if (typeof data?.message === "string") return data.message;

  if (data && typeof data === "object") {
    const firstValue = Object.values(data)[0];

    if (Array.isArray(firstValue)) return firstValue[0];
    if (typeof firstValue === "string") return firstValue;
  }

  return "Something went wrong. Please try again.";
}

function addressLines(value) {
  if (!value || typeof value !== "object") {
    return value ? [String(value)] : [];
  }

  return Object.entries(value)
    .filter(([, item]) => item !== null && item !== undefined && item !== "")
    .filter(([key]) => !["id", "latitude", "longitude"].includes(key))
    .map(([, item]) => {
      if (typeof item === "object") {
        return addressLines(item).join(", ");
      }
      return String(item);
    })
    .filter(Boolean);
}

export default function BookingDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [booking, setBooking] = useState(null);
  const [reasons, setReasons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showCancelForm, setShowCancelForm] = useState(false);
  const [reasonCode, setReasonCode] = useState("");
  const [cancelNote, setCancelNote] = useState("");
  const [cancelError, setCancelError] = useState("");
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadBooking() {
      setLoading(true);
      setError("");

      try {
        const [bookingData, reasonData] = await Promise.all([
          getBooking(id),
          getCancelReasons(),
        ]);

        if (!active) return;

        setBooking(bookingData);
        const customerReasons = reasonData?.customer || [];
        setReasons(customerReasons);
        setReasonCode(customerReasons[0]?.code || "");
      } catch (err) {
        if (active) setError(errorMessage(err));
      } finally {
        if (active) setLoading(false);
      }
    }

    loadBooking();

    return () => {
      active = false;
    };
  }, [id]);

  async function handleCancel(event) {
    event.preventDefault();
    setCancelError("");

    if (!reasonCode) {
      setCancelError("Please select a cancellation reason.");
      return;
    }

    setCancelling(true);

    try {
      const updatedBooking = await cancelBooking(id, {
        reason_code: reasonCode,
        note: cancelNote.trim(),
      });

      setBooking(updatedBooking);
      setShowCancelForm(false);
      setCancelNote("");
    } catch (err) {
      setCancelError(errorMessage(err));
    } finally {
      setCancelling(false);
    }
  }

  if (loading) {
    return (
      <section className="page booking-detail-page">
        <Spinner label="Loading booking details..." />
      </section>
    );
  }

  if (error || !booking) {
    return (
      <section className="page booking-detail-page">
        <Link to="/bookings" className="back-link">
          ← Back to My Bookings
        </Link>
        <div className="bookings-message bookings-message--error" role="alert">
          {error || "Booking not found."}
        </div>
      </section>
    );
  }

  const address = addressLines(booking.address);
  const cancellation = booking.cancellation;

  return (
    <section className="page booking-detail-page">
      <Link to="/bookings" className="back-link">
        ← Back to My Bookings
      </Link>

      <div className="booking-detail-heading">
        <div>
          <p className="bookings-page__eyebrow">BOOKING DETAILS</p>
          <h1>{booking.service?.name || "Service booking"}</h1>
          <p className="muted">
            Reference: {booking.reference || booking.id}
          </p>
        </div>

        <span
          className={`booking-status booking-status--${booking.status}`}
        >
          {statusLabel(booking.status)}
        </span>
      </div>

      <div className="booking-detail-grid">
        <div className="booking-detail-main">
          <section className="booking-detail-card">
            <h2>Schedule</h2>

            <dl className="booking-detail-list">
              <div>
                <dt>Service date and time</dt>
                <dd>{formatDate(booking.scheduled_at)}</dd>
              </div>

              <div>
                <dt>Expected end time</dt>
                <dd>{formatDate(booking.ends_at)}</dd>
              </div>

              <div>
                <dt>Duration</dt>
                <dd>
                  {booking.duration_minutes
                    ? `${booking.duration_minutes} minutes`
                    : "Not available"}
                </dd>
              </div>

              <div>
                <dt>Number of items</dt>
                <dd>{booking.item_count ?? "Not available"}</dd>
              </div>
            </dl>
          </section>

          <section className="booking-detail-card">
            <h2>Service address</h2>

            {address.length > 0 ? (
              <p className="booking-address">
                {address.map((line, index) => (
                  <span key={`${line}-${index}`}>{line}</span>
                ))}
              </p>
            ) : (
              <p className="muted">Address details are not available.</p>
            )}
          </section>

          <section className="booking-detail-card">
            <h2>Service provider</h2>

            {booking.provider ? (
              <div className="booking-provider">
                <strong>{booking.provider.display_name}</strong>
                {booking.provider.phone && (
                  <p>
                    <span className="muted">Phone: </span>
                    {booking.provider.phone}
                  </p>
                )}
              </div>
            ) : (
              <p className="muted">
                Your booking is waiting for a provider to accept it.
                {booking.pending_offers > 0 &&
                  ` ${booking.pending_offers} provider offer(s) are pending.`}
              </p>
            )}
          </section>

          {booking.start_code && (
            <section className="booking-detail-card booking-start-code">
              <h2>Service start code</h2>
              <p>Share this code with your provider when they arrive.</p>
              <strong>{booking.start_code}</strong>
            </section>
          )}

          {booking.customer_notes && (
            <section className="booking-detail-card">
              <h2>Your notes</h2>
              <p>{booking.customer_notes}</p>
            </section>
          )}

          {cancellation && (
            <section className="booking-detail-card booking-cancellation">
              <h2>Cancellation information</h2>

              <dl className="booking-detail-list">
                <div>
                  <dt>Cancelled on</dt>
                  <dd>{formatDate(cancellation.cancelled_at)}</dd>
                </div>
                <div>
                  <dt>Cancelled by</dt>
                  <dd>{cancellation.by || "Not available"}</dd>
                </div>
                <div>
                  <dt>Reason</dt>
                  <dd>{cancellation.reason || cancellation.reason_code}</dd>
                </div>
                <div>
                  <dt>Cancellation timing</dt>
                  <dd>{cancellation.late ? "Late cancellation" : "Within free cancellation period"}</dd>
                </div>
                {cancellation.note && (
                  <div>
                    <dt>Additional note</dt>
                    <dd>{cancellation.note}</dd>
                  </div>
                )}
              </dl>
            </section>
          )}

          {booking.status_history?.length > 0 && (
            <section className="booking-detail-card">
              <h2>Booking timeline</h2>

              <ol className="booking-timeline">
                {booking.status_history.map((item, index) => (
                  <li key={`${item.changed_at}-${index}`}>
                    <span className="booking-timeline__dot" />
                    <div>
                      <strong>{statusLabel(item.to_status)}</strong>
                      <time>{formatDate(item.changed_at)}</time>
                      {item.remarks && <p>{item.remarks}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>

        <aside className="booking-detail-sidebar">
          <section className="booking-detail-card">
            <h2>Price summary</h2>

            <dl className="booking-detail-list">
              <div>
                <dt>Price per unit</dt>
                <dd>
                  {formatMoney(booking.unit_price, booking.currency)}
                </dd>
              </div>

              <div>
                <dt>Discount</dt>
                <dd>
                  {formatMoney(booking.discount_amount, booking.currency)}
                </dd>
              </div>

              <div className="booking-total">
                <dt>Estimated total</dt>
                <dd>
                  {formatMoney(booking.estimated_total, booking.currency)}
                </dd>
              </div>
            </dl>

            <p className="booking-payment-note">
              Payment method:{" "}
              <strong>
                {booking.payment_mode === "online"
                  ? "Online"
                  : booking.payment_mode === "cash"
                    ? "Cash"
                    : booking.payment_mode || "Not available"}
              </strong>
            </p>
            <p className="muted booking-payment-note">
              This is the estimated booking amount. Payment status and invoice
              details are not currently provided by this API.
            </p>
          </section>

          {booking.can_cancel && (
            <section className="booking-detail-card">
              <h2>Cancel booking</h2>

              {!showCancelForm ? (
                <>
                  <p className="muted">
                    You can cancel this booking while it is eligible for
                    cancellation.
                  </p>
                  {booking.free_cancellation_until && (
                    <p className="muted">
                      Free cancellation until:{" "}
                      {formatDate(booking.free_cancellation_until)}
                    </p>
                  )}
                  <button
                    type="button"
                    className="btn btn--ghost booking-cancel-button"
                    onClick={() => setShowCancelForm(true)}
                  >
                    Cancel booking
                  </button>
                </>
              ) : (
                <form className="form" onSubmit={handleCancel}>
                  <label>
                    Cancellation reason
                    <select
                      value={reasonCode}
                      onChange={(event) => setReasonCode(event.target.value)}
                      required
                    >
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
                      rows="3"
                      maxLength="500"
                      value={cancelNote}
                      onChange={(event) => setCancelNote(event.target.value)}
                      placeholder="Tell us more, if needed"
                    />
                  </label>

                  {cancelError && (
                    <div
                      className="bookings-message bookings-message--error"
                      role="alert"
                    >
                      {cancelError}
                    </div>
                  )}

                  <div className="booking-cancel-actions">
                    <button
                      type="button"
                      className="btn btn--ghost"
                      disabled={cancelling}
                      onClick={() => {
                        setShowCancelForm(false);
                        setCancelError("");
                      }}
                    >
                      Go back
                    </button>

                    <button
                      type="submit"
                      className="btn btn--primary"
                      disabled={cancelling || !reasonCode}
                    >
                      {cancelling ? "Cancelling..." : "Confirm cancellation"}
                    </button>
                  </div>
                </form>
              )}
            </section>
          )}

          {booking.status === "cancelled" && (
            <div className="bookings-message">
              This booking has been cancelled.
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}
