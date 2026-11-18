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

  it("login form", () => {
    const html = render("/login");
    expect(html).toContain("Phone number");
    expect(html).toContain("Service provider");
  });

  it("placeholders, protected routes and 404", () => {
    expect(render("/services/3")).toContain("Service details");
    expect(render("/become-a-provider")).toContain("Become a provider");
    expect(render("/bookings")).not.toContain("My Bookings</h1>");   // signed out: redirected to login, not shown
    expect(render("/nope/nothing")).toContain("Page not found");
  });
});
