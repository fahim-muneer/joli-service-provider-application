import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import Button from "../components/Button";
import ErrorMessage from "../components/ErrorMessage";
import { ROLES, homeFor } from "../auth/roles";
import * as authApi from "../api/auth";
import { useAuth } from "../context/AuthContext";
import { getErrorMessage } from "../utils/errors";

// Customers and providers share this page and this form; the `role` prop picks the
// backend endpoint and the few extra fields. (Admins never register here.)
//   /register           -> <Register role="customer" />  -> POST /auth/register/customer/
//   /provider/register  -> <Register role="provider" />  -> POST /auth/register/provider/
const SUBMIT = { customer: authApi.registerCustomer, provider: authApi.registerProvider };

export default function Register({ role = "customer" }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const config = ROLES[role];
  const [form, setForm] = useState({ full_name: "", phone: "", password: "", confirm: "", business_name: "", email: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to={homeFor(user.role)} replace />;

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (form.password !== form.confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      const { confirm, business_name, email, ...body } = form;
      body.password_confirm = confirm; // the backend checks the two passwords itself too
      if (email) body.email = email;
      if (role === "provider") body.business_name = business_name;
      await SUBMIT[role](body);
      // The backend sends an SMS code now but returns no login tokens, so the next step is to log in;
      // Login then sends unverified users to the verify-phone page.
      navigate(config.loginPath, { replace: true, state: { notice: "Account created. We sent a verification code to your phone. Log in to enter it." } });
    } catch (err) {
      setError(getErrorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <section className="narrow">
      <h1>{role === "provider" ? "Become a provider" : "Sign up"}</h1>
      <form className="form" onSubmit={handleSubmit}>
        <label>
          Full name
          <input value={form.full_name} onChange={update("full_name")} autoComplete="name" required />
        </label>
        {role === "provider" && (
          <label>
            Business name
            <input value={form.business_name} onChange={update("business_name")} autoComplete="organization" />
          </label>
        )}
        <label>
          Email{role === "customer" ? " (optional)" : ""}
          <input type="email" value={form.email} onChange={update("email")} autoComplete="email" required={role === "provider"} />
        </label>
        <label>
          Phone number
          <input type="tel" value={form.phone} onChange={update("phone")} autoComplete="tel" required />
        </label>
        <label>
          Password
          <input type="password" value={form.password} onChange={update("password")} autoComplete="new-password" minLength={8} required />
        </label>
        <label>
          Confirm password
          <input type="password" value={form.confirm} onChange={update("confirm")} autoComplete="new-password" required />
        </label>
        <ErrorMessage message={error} />
        <Button type="submit" disabled={submitting}>{submitting ? "Creating account…" : "Create account"}</Button>
      </form>
      <p className="form-links">
        Already have an account? <Link to={config.loginPath}>Log in</Link>
      </p>
    </section>
  );
}
