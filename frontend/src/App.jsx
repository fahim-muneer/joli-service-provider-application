import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import ComingSoon from "./pages/ComingSoon";
import Home from "./pages/Home";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Services from "./pages/Services";

// Pages are added here as the roadmap progresses.
export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="services" element={<Services />} />
        <Route path="services/:id" element={<ComingSoon title="Service details" note="Service details and booking come next." />} />
        <Route path="login" element={<Login />} />
        <Route path="register" element={<ComingSoon title="Sign up" note="Registration pages arrive in Week 3." />} />
        <Route path="become-a-provider" element={<ComingSoon title="Become a provider" note="Partner registration is a separate app." />} />
        <Route element={<ProtectedRoute role="customer" />}>
          <Route path="bookings" element={<ComingSoon title="My Bookings" note="Your bookings will appear here." />} />
          <Route path="account" element={<ComingSoon title="My Account" note="Profile and addresses arrive in Week 3." />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
