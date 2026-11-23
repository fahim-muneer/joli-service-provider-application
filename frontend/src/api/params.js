/** Drop empty values so they do not appear in the query string. */
export function clean(params = {}) {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  );
}
