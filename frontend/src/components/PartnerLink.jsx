import { PROVIDER_APP_URL } from "../config";
import Button from "./Button";

/** Sends people to the separate provider app when one is configured, else to the in-app page. */
export default function PartnerLink({ children, size = "normal", variant = "primary" }) {
  if (PROVIDER_APP_URL) {
    return (
      <a className={`btn btn--${variant} ${size === "large" ? "btn--large" : ""}`.trim()} href={PROVIDER_APP_URL}>
        {children}
      </a>
    );
  }
  return <Button to="/become-a-provider" size={size} variant={variant}>{children}</Button>;
}
