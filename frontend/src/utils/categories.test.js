import { describe, expect, it } from "vitest";
import { categoryBannerUrl, categoryIconUrl, iconKey, initialOf } from "./categories";

describe("category helpers", () => {
  it("normalises the artwork key from the admin's icon field", () => {
    expect(iconKey({ icon: "  Plumber " })).toBe("plumber");
    expect(iconKey({ icon: "" })).toBe("");
    expect(iconKey({})).toBe("");
    expect(iconKey(null)).toBe("");
  });

  it("returns null (so the UI shows a fallback) when there is no artwork", () => {
    expect(categoryIconUrl({ icon: "definitely-not-a-real-key" })).toBeNull();
    expect(categoryBannerUrl({ icon: "" })).toBeNull();
    expect(categoryIconUrl(undefined)).toBeNull();
  });

  it("builds a fallback letter", () => {
    expect(initialOf({ name: "plumbing" })).toBe("P");
    expect(initialOf({ name: "  ac service" })).toBe("A");
    expect(initialOf(undefined)).toBe("?");
  });
});
