/** Labels for a provider's approval_status, shared by the provider dashboard and the admin pages. */
export const PROVIDER_STATUS = {
  pending: { label: "Not submitted", tone: "muted" },
  under_review: { label: "Under review", tone: "info" },
  approved: { label: "Approved", tone: "ok" },
  rejected: { label: "Rejected", tone: "bad" },
  suspended: { label: "Suspended", tone: "bad" },
};

// Admin wording (Figma "Service providers": Needs review / Active / Suspended).
export const ADMIN_PROVIDER_STATUS = {
  pending: { label: "Not submitted", tone: "muted" },
  under_review: { label: "Needs review", tone: "info" },
  approved: { label: "Active", tone: "ok" },
  rejected: { label: "Rejected", tone: "bad" },
  suspended: { label: "Suspended", tone: "bad" },
};

export const DOCUMENT_STATUS = {
  pending: { label: "Waiting for review", tone: "info" },
  approved: { label: "Approved", tone: "ok" },
  rejected: { label: "Rejected", tone: "bad" },
};

export const statusInfo = (table, value) => table[value] ?? { label: String(value ?? ""), tone: "muted" };

export const formatDate = (value) => (value ? new Date(value).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "");

export const initials = (name = "") => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
