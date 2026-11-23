import { describe, expect, it } from "vitest";
import { getErrorMessage } from "./errors";

const withResponse = (status, data) => ({ response: { status, data } });

describe("getErrorMessage", () => {
  it("reads DRF detail strings and lists", () => {
    expect(getErrorMessage(withResponse(400, { detail: "Only approved providers can go online." }))).toBe(
      "Only approved providers can go online.",
    );
    expect(getErrorMessage(withResponse(400, { detail: ["Verify your phone number.", "Upload an ID proof."] }))).toBe(
      "Verify your phone number.",
    );
  });

  it("names the field for validation errors", () => {
    expect(getErrorMessage(withResponse(400, { phone: ["Enter a valid 10-digit Indian mobile number."] }))).toBe(
      "phone: Enter a valid 10-digit Indian mobile number.",
    );
    expect(getErrorMessage(withResponse(400, { new_password: ["Too short."] }))).toBe("new password: Too short.");
    expect(getErrorMessage(withResponse(400, { non_field_errors: ["Send exactly one of: date, dates."] }))).toBe(
      "Send exactly one of: date, dates.",
    );
  });

  it("handles throttling, server and network errors", () => {
    expect(getErrorMessage(withResponse(429, { detail: "Request was throttled." }))).toMatch(/too many attempts/i);
    expect(getErrorMessage(withResponse(500, "<html>"))).toMatch(/server had a problem/i);
    expect(getErrorMessage({ request: {}, message: "Network Error" })).toMatch(/cannot reach the server/i);
    expect(getErrorMessage({ code: "ECONNABORTED" })).toMatch(/too long/i);
  });

  it("falls back for anything unexpected", () => {
    expect(getErrorMessage(null)).toMatch(/something went wrong/i);
    expect(getErrorMessage(withResponse(400, "plain text"))).toMatch(/something went wrong/i);
    expect(getErrorMessage(withResponse(400, {}), "Custom")).toBe("Custom");
  });
});
