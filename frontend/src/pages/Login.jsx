import { useState } from "react";
import { Navigate, useLocation as useRouterLocation, useNavigate } from "react-router-dom";
import Button from "../components/Button";
import ErrorMessage from "../components/ErrorMessage";
import { useAuth } from "../context/AuthContext";
import { getErrorMessage } from "../utils/errors";

// A basic sign-in so the API client can be exercised end to end.
// The finished, styled login and registration pages come in Week 3.
export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const here = useRouterLocation();
  const [form, setForm] = useState({ phone: "", password: "", portal: "customer" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(form);
      navigate(here.state?.from ?? "/", { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="narrow">
      <h1>Log in</h1>
      <form className="form" onSubmit={handleSubmit}>
        <label>
          Phone number
          <input type="tel" value={form.phone} onChange={update("phone")} autoComplete="tel" required />
        </label>
        <label>
          Password
          <input type="password" value={form.password} onChange={update("password")} autoComplete="current-password" required />
        </label>
        <label>
          I am a
          <select value={form.portal} onChange={update("portal")}>
            <option value="customer">Customer</option>
            <option value="provider">Service provider</option>
            <option value="admin">Admin</option>
          </select>
        </label>
        <ErrorMessage message={error} />
        <Button type="submit" disabled={submitting}>{submitting ? "Signing in…" : "Log in"}</Button>
      </form>
    </section>
  );
}
