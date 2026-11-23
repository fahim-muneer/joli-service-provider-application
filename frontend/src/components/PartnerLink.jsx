import Button from "./Button";

/** "Register as a partner" button: goes to the provider registration page. */
export default function PartnerLink({ children, size = "normal", variant = "primary" }) {
  return <Button to="/provider/register" size={size} variant={variant}>{children}</Button>;
}
