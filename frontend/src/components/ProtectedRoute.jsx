import { Navigate, Outlet, useLocation as useRouterLocation } from "react-router-dom";
import { homeFor, loginFor } from "../auth/roles";
import { useAuth } from "../context/useAuth";
import Spinner from "./Spinner";

/** Wrap routes that need a signed-in user of one role ("customer" | "provider" | "admin").
 *  - still checking the saved session -> spinner
 *  - signed out                       -> that role's own login page (remembering where they were going)
 *  - signed in as the WRONG role      -> their own home, never someone else's pages */
export default function ProtectedRoute({ role }) {
  const { user, loading } = useAuth();
  const here = useRouterLocation();

  if (loading) return <Spinner label="Checking your session…" />;
  if (!user) return <Navigate to={loginFor(role)} replace state={{ from: here.pathname + here.search }} />;
  if (role && user.role !== role) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}
