import { useEffect, useState } from "react";
import {
  acceptProviderRequest,
  declineProviderRequest,
  listProviderRequests,
} from "../../api/bookings";
import { getMe } from "../../api/provider";
import Button from "../../components/Button";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import { getErrorMessage } from "../../utils/errors";
import "../../styles/provider-requests.css";

function formatDate(value) {
  if (!value) return "Not specified";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Not specified";

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatMoney(value, currency = "INR") {
  const amount = Number(value);

  if (!Number.isFinite(amount)) return "—";

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

function RequestCard({ request, approved, busy, onAccept, onDecline }) {
  const [reason, setReason] = useState("");
  const booking = request.booking || {};

  return (
    <article className="provider-request">
      <div className="provider-request__header">
        <div>
          <span className="provider-request__reference">
            {booking.reference || `Request #${request.id}`}
          </span>
          <h2>{booking.service || "Service request"}</h2>
        </div>

        <span className="provider-request__status">New request</span>
      </div>

      <div className="provider-request__price">
        <span>Estimated amount</span>
        <strong>
          {formatMoney(booking.estimated_total, booking.currency)}
        </strong>
      </div>

      <div className="provider-request__details">
        <div>
          <span>Scheduled date</span>
          <strong>{formatDate(booking.scheduled_at)}</strong>
        </div>

        <div>
          <span>Duration</span>
          <strong>
            {booking.duration_minutes
              ? `${booking.duration_minutes} minutes`
              : "Not specified"}
          </strong>
        </div>

        <div>
          <span>Location</span>
          <strong>
            {[booking.area, booking.city].filter(Boolean).join(", ") || "Not specified"}
          </strong>
        </div>

        <div>
          <span>Pincode</span>
          <strong>{booking.pincode || "Not specified"}</strong>
        </div>

        <div>
          <span>Number of items</span>
          <strong>{booking.item_count ?? 1}</strong>
        </div>

        <div>
          <span>Payment method</span>
          <strong>
            {booking.payment_mode === "cash"
              ? "Cash"
              : booking.payment_mode === "online"
                ? "Online"
                : booking.payment_mode || "Not specified"}
          </strong>
        </div>

        <div>
          <span>Unit price</span>
          <strong>{formatMoney(booking.unit_price, booking.currency)}</strong>
        </div>

        <div>
          <span>Offer expires</span>
          <strong>{formatDate(request.expires_at)}</strong>
        </div>
      </div>

      {booking.notes && (
        <div className="provider-request__notes">
          <strong>Customer notes</strong>
          <p>{booking.notes}</p>
        </div>
      )}

      <p className="provider-request__privacy">
        Customer contact details and exact address will be available after
        accepting this request.
      </p>

      <div className="provider-request__actions">
        <div className="provider-request__decline">
          <label htmlFor={`decline-reason-${request.id}`}>
            Reason for declining (optional)
          </label>
          <input
            id={`decline-reason-${request.id}`}
            type="text"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Enter a reason"
            maxLength={500}
            disabled={busy}
          />
        </div>

        <div className="provider-request__buttons">
          <Button
            disabled={busy}
            onClick={() => onDecline(request.id, reason)}
          >
            {busy ? "Please wait…" : "Decline"}
          </Button>

          <Button
            disabled={busy || !approved}
            onClick={() => onAccept(request.id)}
          >
            {busy ? "Please wait…" : "Accept request"}
          </Button>
        </div>
      </div>
    </article>
  );
}

export default function Requests() {
  const [requests, setRequests] = useState([]);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const [requestData, providerData] = await Promise.all([
          listProviderRequests(),
          getMe(),
        ]);

        if (!active) return;

        setRequests(Array.isArray(requestData) ? requestData : []);
        setProfile(providerData);
      } catch (err) {
        if (active) setError(getErrorMessage(err));
      } finally {
        if (active) setLoading(false);
      }
    }

    load();

    return () => {
      active = false;
    };
  }, [reloadKey]);

  const approved = profile?.approval_status === "approved";

  async function handleAccept(id) {
    setBusyId(id);
    setActionError("");

    try {
      await acceptProviderRequest(id);
      setReloadKey((value) => value + 1);
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDecline(id, reason) {
    setBusyId(id);
    setActionError("");

    try {
      await declineProviderRequest(id, reason);
      setReloadKey((value) => value + 1);
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  if (loading && !profile) {
    return <Spinner label="Loading booking requests…" />;
  }

  if (error && !profile) {
    return <ErrorMessage message={error} onRetry={() => setReloadKey((v) => v + 1)} />;
  }

  return (
    <section className="provider-requests-page">
      <div className="provider-requests-page__intro">
        <div>
          <h2>Incoming requests</h2>
          <p>Review service requests from customers in your service areas.</p>
        </div>

        <Button
          disabled={loading || busyId !== null}
          onClick={() => setReloadKey((value) => value + 1)}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </Button>
      </div>

      {!approved && (
        <div className="provider-request-notice">
          Your provider account is not approved yet. You can view and decline
          requests, but you must be approved before accepting a booking.
        </div>
      )}

      <ErrorMessage message={error || actionError} />

      {loading && profile && (
        <Spinner label="Refreshing requests…" />
      )}

      {!loading && requests.length === 0 && (
        <div className="provider-request-empty">
          <h2>No new requests</h2>
          <p>
            New customer booking requests will appear here when a matching
            service and available time are found.
          </p>
        </div>
      )}

      {!loading && requests.length > 0 && (
        <div className="provider-requests-list">
          {requests.map((request) => (
            <RequestCard
              key={request.id}
              request={request}
              approved={approved}
              busy={busyId === request.id}
              onAccept={handleAccept}
              onDecline={handleDecline}
            />
          ))}
        </div>
      )}
    </section>
  );
}