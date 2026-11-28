
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createAddress, listAddresses } from "../api/addresses";
import { createBooking } from "../api/bookings";
import { listAreas } from "../api/catalog";
import Button from "./Button";
import ErrorMessage from "./ErrorMessage";
import Spinner from "./Spinner";
import { getErrorMessage } from "../utils/errors";

function minimumDateTime() {
  const date = new Date(Date.now() + 60 * 60 * 1000);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

export default function BookingForm({
  service,
  provider,
  cityId,
  initialDateTime,
  onClose,
}) {
  const minDateTime = minimumDateTime();

  const [addresses, setAddresses] = useState([]);
  const [areas, setAreas] = useState([]);
  const [addressId, setAddressId] = useState("");
  const [addingAddress, setAddingAddress] = useState(false);
  const [addressForm, setAddressForm] = useState({
    label: "Home",
    address_line: "",
    landmark: "",
    area: "",
  });

  const [scheduledAt, setScheduledAt] = useState(
    initialDateTime && initialDateTime >= minDateTime
      ? initialDateTime
      : minDateTime
  );
  const [paymentMode, setPaymentMode] = useState("cash");
  const [itemCount, setItemCount] = useState(1);
  const [notes, setNotes] = useState("");

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      listAddresses(),
      cityId ? listAreas(cityId) : Promise.resolve([]),
    ])
      .then(([addressData, areaData]) => {
        if (cancelled) return;

        const saved = Array.isArray(addressData)
          ? addressData
          : addressData.results ?? [];

        setAddresses(saved);
        setAddressId(String(saved.find((a) => a.is_default)?.id ?? saved[0]?.id ?? ""));
        setAreas(Array.isArray(areaData) ? areaData : areaData.results ?? []);

        if (saved.length === 0) setAddingAddress(true);
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [cityId]);

  function updateAddressField(event) {
    const { name, value } = event.target;
    setAddressForm((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);

    try {
      let selectedAddressId = addressId;

      if (addingAddress) {
        if (!cityId) {
          throw new Error("Please select your city before adding an address.");
        }

        if (!addressForm.area) {
          throw new Error("Please select an area.");
        }

        const savedAddress = await createAddress({
          ...addressForm,
          area: Number(addressForm.area),
        });

        selectedAddressId = String(savedAddress.id);
        setAddresses((current) => [...current, savedAddress]);
        setAddressId(selectedAddressId);
      }

      if (!selectedAddressId) {
        throw new Error("Please select or add a service address.");
      }

      if (scheduledAt < minimumDateTime()) {
        throw new Error("Please choose a time at least one hour from now.");
      }

      const payload = {
        service: service.id,
        address: Number(selectedAddressId),
        scheduled_at: new Date(scheduledAt).toISOString(),
        item_count: Number(itemCount),
        notes,
        payment_mode: paymentMode,
      };

      if (provider?.provider) {
        payload.provider = provider.provider;
      }

      const booking = await createBooking(payload);
      setSuccess(booking);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (success) {
    return (
      <div className="booking-overlay">
        <section className="booking-dialog" role="dialog" aria-modal="true">
          <h2>Booking request submitted!</h2>
          <p>Your booking reference is:</p>
          <strong>{success.reference}</strong>
          <p>Status: {success.status}</p>
          <p>Estimated total: ₹{success.estimated_total}</p>
          <div className="booking-actions">
            <Button to="/bookings">View my bookings</Button>
            <Button variant="ghost" onClick={onClose}>Close</Button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="booking-overlay">
      <section
        className="booking-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="booking-title"
      >
        <div className="booking-dialog__header">
          <div>
            <h2 id="booking-title">Book {service.name}</h2>
            {provider && <p>Provider: {provider.display_name}</p>}
          </div>
          <button type="button" onClick={onClose} aria-label="Close booking form">
            ×
          </button>
        </div>

        {loading ? (
          <Spinner label="Loading your saved addresses…" />
        ) : (
          <form className="form" onSubmit={handleSubmit}>
            {addresses.length > 0 && (
              <label>
                Select service address
                <select
                  value={addingAddress ? "" : addressId}
                  onChange={(e) => {
                    setAddressId(e.target.value);
                    setAddingAddress(false);
                  }}
                  required={!addingAddress}
                >
                  <option value="">Choose an address</option>
                  {addresses.map((address) => (
                    <option key={address.id} value={address.id}>
                      {address.label} — {address.address_line}, {address.area_name}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <Button
              type="button"
              variant="ghost"
              size="small"
              onClick={() => setAddingAddress((value) => !value)}
            >
              {addingAddress ? "Choose saved address" : "＋ Add new address"}
            </Button>

            {addingAddress && (
              <>
                <label>
                  Address label
                  <select
                    name="label"
                    value={addressForm.label}
                    onChange={updateAddressField}
                  >
                    <option value="Home">Home</option>
                    <option value="Work">Work</option>
                    <option value="Other">Other</option>
                  </select>
                </label>

                <label>
                  Full address
                  <input
                    name="address_line"
                    value={addressForm.address_line}
                    onChange={updateAddressField}
                    minLength={5}
                    required
                    placeholder="House name, street, locality"
                  />
                </label>

                <label>
                  Landmark (optional)
                  <input
                    name="landmark"
                    value={addressForm.landmark}
                    onChange={updateAddressField}
                    placeholder="Near a landmark"
                  />
                </label>

                <label>
                  Area
                  <select
                    name="area"
                    value={addressForm.area}
                    onChange={updateAddressField}
                    required
                    disabled={!cityId || areas.length === 0}
                  >
                    <option value="">Select area</option>
                    {areas.map((area) => (
                      <option key={area.id} value={area.id}>
                        {area.name} {area.pincode ? `(${area.pincode})` : ""}
                      </option>
                    ))}
                  </select>
                </label>

                {!cityId && (
                  <p className="muted">Select a city in the page header first.</p>
                )}
                {cityId && areas.length === 0 && (
                  <p className="muted">No active areas are available in this city.</p>
                )}
              </>
            )}

            <label>
              Date and time
              <input
                type="datetime-local"
                min={minDateTime}
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                required
              />
            </label>

            <label>
              Number of items
              <input
                type="number"
                min="1"
                max="50"
                value={itemCount}
                onChange={(e) => setItemCount(e.target.value)}
                required
              />
            </label>

            <label>
              Payment method
              <select
                value={paymentMode}
                onChange={(e) => setPaymentMode(e.target.value)}
              >
                <option value="cash">Cash after service</option>
                <option value="online">Online payment</option>
              </select>
            </label>

            <label>
              Additional instructions (optional)
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={1000}
                rows={3}
              />
            </label>

            <ErrorMessage message={error} />

            <div className="booking-actions">
              <Button type="submit" disabled={busy || loading}>
                {busy ? "Submitting…" : "Confirm booking"}
              </Button>
              <Button type="button" variant="ghost" onClick={onClose}>
                Cancel
              </Button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
