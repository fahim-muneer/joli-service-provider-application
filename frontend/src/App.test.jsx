import { renderToString } from "react-dom/server";
import { StaticRouter } from "react-router-dom/server";
import { describe, expect, it } from "vitest";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { LocationProvider } from "./context/LocationContext";

// Smoke tests: every route renders without crashing (server-side render, no browser needed).
function render(path) {
  return renderToString(
    <StaticRouter location={path}>
      <AuthProvider>
        <LocationProvider>
          <App />
        </LocationProvider>
      </AuthProvider>
    </StaticRouter>,
  );
}

describe("layout", () => {
  const html = render("/");
  it("has the header from the design", () => {
    for (const text of ["Joli", "Login", "Home", "My Bookings", "Services", "Become a Provider", "Your Location", "Search services"]) {
      expect(html).toContain(text);
    }
    expect(html).toContain("Skip to content");
  });
  it("has the location popup markup", () => {
    expect(html).toContain("Select Your location to continue");
    expect(html).toContain("<dialog");
  });
  it("has the footer and the Why Joli strip", () => {
    for (const text of ["WHY JOLI?", "Transparent Pricing", "Cancellation Policy", "Uncomplicate Life!", "Follow Us"]) {
      expect(html).toContain(text);
    }
  });
});

describe("routes", () => {
  it("home: most used services and the partner banner", () => {
    const html = render("/");
    expect(html).toContain("Most Used Services");
    expect(html).toContain("Are you a service expert?");
    expect(html).toContain("Register as a partner");
  });

  it("services: category row and search heading", () => {
    const html = render("/services?category=plumbing");
    expect(html).toContain("Service Categories");
    expect(html).toContain("All service");
    expect(render("/services?search=tap")).toContain("Results for");
  });

  it("three separate login pages, no role dropdown", () => {
    const customer = render("/login");
    expect(customer).toContain("Phone number");
    expect(customer).toContain("Provider login");
    expect(customer).not.toContain("<select");
    expect(render("/provider/login")).toContain("Service provider log in");
    expect(render("/provider/login")).toContain("Join Largest Service Network"); // Figma login card
    expect(render("/admin/login")).toContain("Welcome back admin"); // Figma admin login
    expect(render("/admin/login")).toContain("Email");
    expect(render("/admin/login")).not.toContain("Create an account"); // admins do not self-register
  });

  it("role-based registration", () => {
    expect(render("/register")).toContain("Sign up");
    expect(render("/register")).toContain("Email");
    const provider = render("/provider/register");
    expect(provider).toContain("Become a provider");
    expect(provider).toContain("Business name");
    expect(provider).toContain("Email");
  });

  it("phone verification (OTP) pages need a login", () => {
    expect(render("/verify-phone")).not.toContain("Verify your phone");
    expect(render("/provider/verify-phone")).not.toContain("Verify your phone");
  });

  it("provider and admin areas are locked when signed out", () => {
    const locked = { "/provider": "Application status", "/provider/documents": "Your documents", "/provider/services": "What you offer",
      "/provider/areas": "Service areas", "/provider/schedule": "Upcoming", "/provider/profile": "About you" };
    for (const [path, text] of Object.entries(locked)) {
      expect(render(path)).not.toContain(text); // signed out: redirected to the provider login
    }
    expect(render("/admin")).not.toContain("ADMIN PORTAL");
    expect(render("/admin/providers")).not.toContain("Service Providers");
    expect(render("/admin/providers/1")).not.toContain("Decision");
  });

  it("placeholders, protected routes and 404", () => {
    expect(render("/services/3")).toContain("Loading service");
    expect(render("/bookings")).not.toContain("My Bookings</h1>");   // signed out: redirected to login, not shown
    expect(render("/nope/nothing")).toContain("Page not found");
  });
});
