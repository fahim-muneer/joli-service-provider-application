import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import Button from "../components/Button";
import ErrorMessage from "../components/ErrorMessage";
import { homeFor } from "../auth/roles";
import { confirmPhoneCode, sendPhoneCode } from "../api/auth";
import { useAuth } from "../context/AuthContext";
import { getErrorMessage } from "../utils/errors";

// The backend sets a 60 second wait between codes.
const RESEND_SECONDS = 60;

/** Phone OTP, same page for customers and providers (each inside its own ProtectedRoute):
 *    /verify-phone           customer
 *    /provider/verify-phone  provider
 *  The backend already sent the first code when the account was created, and it knows
 *  the phone number from the login token, so the person only types the 6 digits. */
export default function VerifyPhone() {
  const { user, updateUser } = useAuth();
  const navigate = useNavigate();
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  if (user.is_phone_verified) return <Navigate to={homeFor(user.role)} replace />;

  async function handleConfirm(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    setBusy(true);
    try {
      const { user: verified } = await confirmPhoneCode({ otp });
      updateUser(verified); // the page above now sees is_phone_verified = true
      navigate(homeFor(verified.role), { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
      setBusy(false);
    }
  }

  async function handleResend() {
    setError("");
    setInfo("");
    setBusy(true);
    try {
      await sendPhoneCode();
      setInfo("A new code has been sent.");
      setCooldown(RESEND_SECONDS);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="narrow">
      <h1>Verify your phone</h1>
      <p className="form-links">Enter the 6-digit code we sent to {user.phone}.</p>
      {user.role === "provider" && (
        <p className="form-links">Providers must verify their phone before they can submit for review.</p>
      )}
      <form className="form" onSubmit={handleConfirm}>
        <label>
          Verification code
          <input
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            required
          />
        </label>
        {info && <p className="notice" role="status">{info}</p>}
        <ErrorMessage message={error} />
        <Button type="submit" disabled={busy || otp.length !== 6}>{busy ? "Checking…" : "Verify"}</Button>
        <Button variant="ghost" disabled={busy || cooldown > 0} onClick={handleResend}>
          {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
        </Button>
      </form>
    </section>
  );
}
