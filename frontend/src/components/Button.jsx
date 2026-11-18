import { Link } from "react-router-dom";

/** variant: "primary" | "ghost"; size: "normal" | "small" | "large".
 *  Pass `to` to render a link that looks like a button. */
export default function Button({ to, variant = "primary", size = "normal", className = "", ...props }) {
  const classes = `btn btn--${variant} ${size === "small" ? "btn--small" : ""} ${size === "large" ? "btn--large" : ""} ${className}`.trim().replace(/\s+/g, " ");
  if (to) return <Link to={to} className={classes} {...props} />;
  return <button type="button" className={classes} {...props} />;
}
