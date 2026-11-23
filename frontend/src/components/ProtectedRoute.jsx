import { Navigate, Outlet, useLocation as useRouterLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Spinner from "./Spinner";

/** Wrap routes that need a signed-in user. `role` limits them to one role
 *  ("customer" | "provider" | "admin"). Wrong role goes home; signed out goes to login. */
export default function ProtectedRoute({ role }) {
  const { user, loading } = useAuth();
  const here = useRouterLocation();

  if (loading) return <Spinner label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: here.pathname + here.search }} />;
  if (role && user.role !== role) return <Navigate to="/" replace />;
  return <Outlet />;
}
