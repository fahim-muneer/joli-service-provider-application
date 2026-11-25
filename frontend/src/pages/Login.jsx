import { useState } from "react";
import { Link, Navigate, useLocation as useRouterLocation } from "react-router-dom";
import Button from "../components/Button";
import ErrorMessage from "../components/ErrorMessage";
import { ROLES, homeFor } from "../auth/roles";
import { useAuth } from "../context/useAuth";
import { getErrorMessage } from "../utils/errors";

/** One login page, three doors. The route decides which one:
 *    /login            -> <Login portal="customer" />
 *    /provider/login   -> <Login portal="provider" />
 *    /admin/login      -> <Login portal="admin" />
 *  The person never picks their role; the page they are on says it, and the backend
 *  refuses an account that does not belong to this portal. */
export default function Login({ portal = "customer" }) {
  const { user, login } = useAuth();
  const here = useRouterLocation();
  const role = ROLES[portal];
  const [form, setForm] = useState({ phone: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Already signed in (or just signed in): go back to where they were headed, else to their own home.
  // Doing the redirect here (not inside handleSubmit) means there is only one place that navigates.
  if (user) {
    const mustVerify = user.role !== "admin" && !user.is_phone_verified;
    return <Navigate to={mustVerify ? ROLES[user.role].verifyPath : (here.state?.from ?? homeFor(user.role))} replace />;
  }

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login({ ...form, portal });
    } catch (err) {
      setError(getErrorMessage(err));
      setSubmitting(false);
    }
    // On success `user` is set and the redirect above runs, so nothing else to do.
  }

  return (
    <section className="narrow">
      <h1>{portal === "customer" ? "Log in" : portal === "admin" ? "Login" : `${role.label} log in`}</h1>
      {here.state?.notice && <p className="notice" role="status">{here.state.notice}</p>}
      <form className="form" onSubmit={handleSubmit}>
        <label>
          Phone number
          <input type="tel" value={form.phone} onChange={update("phone")} autoComplete="tel" required />
        </label>
        <label>
          Password
          <input type="password" value={form.password} onChange={update("password")} autoComplete="current-password" required />
        </label>
        <ErrorMessage message={error} />
        <Button type="submit" disabled={submitting}>{submitting ? "Signing in…" : portal === "admin" ? "Sign in" : "Log in"}</Button>
      </form>

      <p className="form-links">
        {role.registerPath && (
          <>New here? <Link to={role.registerPath}>Create an account</Link></>
        )}
        {portal === "customer" && <> · <Link to={ROLES.provider.loginPath}>Provider login</Link></>}
        {portal === "provider" && <> · <Link to={ROLES.customer.loginPath}>Customer login</Link></>}
      </p>
    </section>
  );
}
