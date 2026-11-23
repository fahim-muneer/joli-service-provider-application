import MockAdapter from "axios-mock-adapter";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, rawApi, setSessionExpiredHandler } from "./client";
import { tokenStore } from "./tokenStore";

let apiMock;
let rawMock;

beforeEach(() => {
  apiMock = new MockAdapter(api);
  rawMock = new MockAdapter(rawApi);
  tokenStore.clear();
  setSessionExpiredHandler(null);
});

const signIn = (access = "old-access", refresh = "old-refresh") => tokenStore.set({ access, refresh });

describe("request interceptor", () => {
  it("sends the access token", async () => {
    signIn();
    apiMock.onGet("/ping").reply((config) => [200, { auth: config.headers.Authorization }]);
    const { data } = await api.get("/ping");
    expect(data.auth).toBe("Bearer old-access");
  });

  it("sends nothing when signed out, and nothing for skipAuth requests", async () => {
    apiMock.onGet("/ping").reply((config) => [200, { auth: config.headers.Authorization ?? null }]);
    expect((await api.get("/ping")).data.auth).toBeNull();
    signIn();
    expect((await api.get("/ping", { skipAuth: true })).data.auth).toBeNull();
  });
});

describe("401 handling", () => {
  it("refreshes once, retries the request, and stores the ROTATED refresh token", async () => {
    signIn();
    apiMock.onGet("/me").reply((config) =>
      config.headers.Authorization === "Bearer new-access" ? [200, { ok: true }] : [401, { detail: "expired" }],
    );
    rawMock.onPost("/auth/token/refresh/").reply((config) => {
      expect(JSON.parse(config.data)).toEqual({ refresh: "old-refresh" });
      return [200, { access: "new-access", refresh: "new-refresh" }];
    });

    const { data } = await api.get("/me");
    expect(data).toEqual({ ok: true });
    expect(tokenStore.getAccess()).toBe("new-access");
    expect(tokenStore.getRefresh()).toBe("new-refresh"); // the old one is dead server-side
    expect(rawMock.history.post).toHaveLength(1);
  });

  it("shares ONE refresh between simultaneous 401s", async () => {
    signIn();
    apiMock.onGet(/\/(a|b|c)$/).reply((config) =>
      config.headers.Authorization === "Bearer new-access" ? [200, { ok: true }] : [401, {}],
    );
    rawMock.onPost("/auth/token/refresh/").reply(
      () => new Promise((resolve) => setTimeout(() => resolve([200, { access: "new-access", refresh: "new-refresh" }]), 20)),
    );

    const results = await Promise.all([api.get("/a"), api.get("/b"), api.get("/c")]);
    expect(results.map((r) => r.status)).toEqual([200, 200, 200]);
    expect(rawMock.history.post).toHaveLength(1); // a second refresh would have used the dead token
  });

  it("clears the session and notifies the app when the refresh fails", async () => {
    signIn();
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    apiMock.onGet("/me").reply(401, { detail: "expired" });
    rawMock.onPost("/auth/token/refresh/").reply(401, { detail: "blacklisted" });

    await expect(api.get("/me")).rejects.toMatchObject({ response: { status: 401 } });
    expect(tokenStore.getAccess()).toBeNull();
    expect(tokenStore.getRefresh()).toBeNull();
    expect(expired).toHaveBeenCalledTimes(1);
  });

  it("does not loop if the retried request is still 401", async () => {
    signIn();
    apiMock.onGet("/me").reply(401, {});
    rawMock.onPost("/auth/token/refresh/").reply(200, { access: "new-access", refresh: "new-refresh" });

    await expect(api.get("/me")).rejects.toMatchObject({ response: { status: 401 } });
    expect(rawMock.history.post).toHaveLength(1);
    expect(apiMock.history.get).toHaveLength(2); // the original + exactly one retry
  });

  it("does not try to refresh when there is no refresh token", async () => {
    apiMock.onGet("/me").reply(401, {});
    await expect(api.get("/me")).rejects.toMatchObject({ response: { status: 401 } });
    expect(rawMock.history.post).toHaveLength(0);
  });

  it("does not refresh for skipAuth requests such as a wrong-password login", async () => {
    signIn();
    apiMock.onPost("/auth/login/").reply(401, { detail: "No active account" });
    await expect(api.post("/auth/login/", {}, { skipAuth: true })).rejects.toMatchObject({ response: { status: 401 } });
    expect(rawMock.history.post).toHaveLength(0);
    expect(tokenStore.getRefresh()).toBe("old-refresh"); // the saved session is untouched
  });

  it("passes other errors through untouched", async () => {
    signIn();
    apiMock.onGet("/x").reply(403, { detail: "no" });
    await expect(api.get("/x")).rejects.toMatchObject({ response: { status: 403 } });
    expect(rawMock.history.post).toHaveLength(0);
  });
});
