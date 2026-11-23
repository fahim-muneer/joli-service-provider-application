/** Turn whatever the API (Django REST Framework) or the network gave us into one
 *  readable sentence for the user. */
export function getErrorMessage(error, fallback = "Something went wrong. Please try again.") {
  if (!error) return fallback;
  if (error.code === "ECONNABORTED") return "The server took too long to respond.";
  if (!error.response) return "Cannot reach the server. Check your connection.";

  const { status, data } = error.response;
  if (status === 429) return "Too many attempts. Please wait a moment and try again.";
  if (status >= 500) return "The server had a problem. Please try again later.";

  const first = (value) => (Array.isArray(value) ? first(value[0]) : value);
  if (typeof data === "string") return fallback;
  if (data?.detail) return String(first(data.detail));
  if (data && typeof data === "object") {
    const [field, messages] = Object.entries(data)[0] ?? [];
    if (messages !== undefined) {
      const text = String(first(messages));
      return field === "non_field_errors" ? text : `${field.replace(/_/g, " ")}: ${text}`;
    }
  }
  return fallback;
}
