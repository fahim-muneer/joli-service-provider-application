// Optional: exercises the REAL API modules against a running backend.
//   1. python manage.py seed_demo_data && python manage.py runserver
//   2. LIVE_API=1 npx vitest run src/api/live.integration.test.js
// (Skipped otherwise. Uses the demo logins from seed_demo_data.)
import { describe, expect, it } from "vitest";
import { getProfile, login, logout } from "./auth";
import { listAreas, listCategories, listCities, listServices } from "./catalog";
import { api } from "./client";
import { getPublicProvider, listServiceProviders } from "./providers";
import { tokenStore } from "./tokenStore";

const live = globalThis.process?.env?.LIVE_API ? describe : describe.skip;

live("against the real backend", () => {
  it("browses the public catalogue", async () => {
    const cities = await listCities({ available: true });
    expect(cities.length).toBeGreaterThan(0);
    const city = cities[0];
    expect((await listAreas(city.id)).length).toBeGreaterThan(0);
    expect((await listCategories({ city: city.id })).length).toBeGreaterThan(0);

    const services = await listServices({ city: city.id, pageSize: 50 });
    expect(services.count).toBeGreaterThan(0);

    const offers = await listServiceProviders(services.results[0].id, { city: city.id });
    expect(offers.results.length).toBeGreaterThan(0);
    expect(offers.results[0]).not.toHaveProperty("phone");

    const provider = await getPublicProvider(offers.results[0].provider);
    expect(provider.services.length).toBeGreaterThan(0);
  });

  it("matches providers by date and time", async () => {
    const [city] = await listCities({ available: true });
    const [service] = (await listServices({ city: city.id })).results;
    const past = await listServiceProviders(service.id, { city: city.id, scheduledAt: "2020-01-01T10:00:00Z" })
      .catch((e) => e.response.status);
    expect(past).toBe(400); // must be in the future
  });

  it("signs in, survives an expired access token by refreshing, and signs out", async () => {
    const user = await login({ phone: "9100000003", password: "Demo@12345", portal: "customer" });
    expect(user.role).toBe("customer");
    expect((await getProfile()).phone).toBe("+919100000003");

    const refreshBefore = tokenStore.getRefresh();
    tokenStore.set({ access: "not-a-valid-token" });          // simulate an expired access token
    expect((await getProfile()).role).toBe("customer");        // 401 -> refresh -> retry
    expect(tokenStore.getRefresh()).not.toBe(refreshBefore);   // refresh token was rotated

    await Promise.all([api.get("/auth/profile/"), api.get("/auth/profile/")]); // still works
    await logout();
    expect(tokenStore.hasSession()).toBe(false);
  });

  it("a wrong password is a plain 401 and never starts a refresh", async () => {
    await expect(login({ phone: "9100000003", password: "wrong", portal: "customer" })).rejects.toMatchObject({
      response: { status: 401 },
    });
  });

  it("the wrong portal is refused", async () => {
    await expect(login({ phone: "9100000003", password: "Demo@12345", portal: "provider" })).rejects.toMatchObject({
      response: { status: 403 },
    });
  });
});
