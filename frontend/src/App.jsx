import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import AdminShell from "./components/portal/AdminShell";
import AuthFrame from "./components/portal/AuthFrame";
import ProviderShell from "./components/portal/ProviderShell";
import ProtectedRoute from "./components/ProtectedRoute";
import ComingSoon from "./pages/ComingSoon";
import Home from "./pages/Home";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import PortalSoon from "./pages/PortalSoon";
import Register from "./pages/Register";
import ServiceDetails from "./pages/ServiceDetails";
import Services from "./pages/Services";
import VerifyPhone from "./pages/VerifyPhone";
import Bookings from "./pages/Bookings";
import BookingDetail from "./pages/BookingDetail";
import AdminCategories from "./pages/admin/Categories";
import AdminDashboard from "./pages/admin/Dashboard";
import AdminProviderDetail from "./pages/admin/ProviderDetail";
import AdminProviders from "./pages/admin/Providers";
import ProviderAreas from "./pages/provider/Areas";
import ProviderDocuments from "./pages/provider/Documents";
import ProviderOverview from "./pages/provider/Overview";
import ProviderProfile from "./pages/provider/Profile";
import ProviderSchedule from "./pages/provider/Schedule";
import ProviderServices from "./pages/provider/Services";
import ProviderRequests from "./pages/provider/Requests";
import ProviderBookings from "./pages/provider/Bookings";
import Notifications from "./pages/portal/Notifications";

export default function App() {
  return (
    <Routes>
      {/* Customer portal */}
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="services" element={<Services />} />
        <Route path="services/:id" element={<ServiceDetails />} />
        <Route path="login" element={<Login portal="customer" />} />
        <Route path="register" element={<Register role="customer" />} />
        <Route
          path="become-a-provider"
          element={<Navigate to="/provider/register" replace />}
        />

        <Route element={<ProtectedRoute role="customer" />}>
          <Route
            path="verify-phone"
            element={<VerifyPhone role="customer" />}
          />
          <Route
            path="notifications"
            element={<Notifications basePath="/" />}
          />
          <Route path="bookings" element={<Bookings />} />
          <Route path="bookings/:id" element={<BookingDetail />} />
          <Route
            path="account"
            element={
              <ComingSoon
                title="My Account"
                note="Profile and addresses arrive in Week 3."
              />
            }
          />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Route>

      {/* Provider portal */}
      <Route path="provider">
        <Route element={<AuthFrame portal="provider" />}>
          <Route path="login" element={<Login portal="provider" />} />
          <Route path="register" element={<Register role="provider" />} />

          <Route element={<ProtectedRoute role="provider" />}>
            <Route
              path="verify-phone"
              element={<VerifyPhone role="provider" />}
            />
          </Route>
        </Route>

        <Route element={<ProtectedRoute role="provider" />}>
          <Route element={<ProviderShell />}>
            <Route index element={<ProviderOverview />} />
            <Route path="profile" element={<ProviderProfile />} />
            <Route path="services" element={<ProviderServices />} />
            <Route path="areas" element={<ProviderAreas />} />
            <Route path="documents" element={<ProviderDocuments />} />
            <Route path="schedule" element={<ProviderSchedule />} />
            <Route path="requests" element={<ProviderRequests />} />
            <Route path="requests" element={<ProviderRequests />} />
            <Route path="bookings" element={<ProviderBookings />} />
            <Route
              path="earnings"
              element={
                <PortalSoon note="Your earnings will appear here once bookings are added." />
              }
            />
            <Route
              path="notifications"
              element={<Notifications basePath="/provider" />}
            />
            <Route
              path="payment"
              element={<PortalSoon note="Payment details are coming soon." />}
            />
          </Route>
        </Route>
      </Route>

      {/* Admin portal */}
      <Route path="admin">
        <Route element={<AuthFrame portal="admin" />}>
          <Route path="login" element={<Login portal="admin" />} />
        </Route>

        <Route element={<ProtectedRoute role="admin" />}>
          <Route element={<AdminShell />}>
            <Route index element={<AdminDashboard />} />
            <Route path="providers" element={<AdminProviders />} />
            <Route
              path="providers/:id"
              element={<AdminProviderDetail />}
            />
            <Route
              path="customers"
              element={
                <PortalSoon
                  heading="Customers"
                  note="Customer management is coming soon."
                />
              }
            />
            <Route path="categories" element={<AdminCategories />} />
            <Route
              path="services"
              element={
                <PortalSoon
                  heading="Services"
                  note="Service management is coming soon."
                />
              }
            />
            <Route
              path="areas"
              element={
                <PortalSoon
                  heading="Areas"
                  note="Area management is coming soon."
                />
              }
            />
            <Route
              path="bookings"
              element={
                <PortalSoon
                  heading="Bookings"
                  note="Bookings are coming soon."
                />
              }
            />
            <Route
              path="reviews"
              element={
                <PortalSoon
                  heading="Reviews & Ratings"
                  note="Reviews are coming soon."
                />
              }
            />
            <Route
              path="payments"
              element={
                <PortalSoon
                  heading="Collections & Payouts"
                  note="Payouts are coming soon."
                />
              }
            />
            <Route
              path="notifications"
              element={<Notifications basePath="/admin" />}
            />
            <Route
              path="settings"
              element={
                <PortalSoon
                  heading="Settings"
                  note="Settings are coming soon."
                />
              }
            />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}