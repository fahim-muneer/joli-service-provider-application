import { statusInfo } from "../utils/status";

/** A small coloured pill. `table` is PROVIDER_STATUS or DOCUMENT_STATUS. */
export default function StatusBadge({ table, value }) {
  const { label, tone } = statusInfo(table, value);
  return <span className={`status status--${tone}`}>{label}</span>;
}
