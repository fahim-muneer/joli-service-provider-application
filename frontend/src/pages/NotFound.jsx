import Button from "../components/Button";

export default function NotFound() {
  return (
    <section className="narrow empty-page">
      <h1>Page not found</h1>
      <p>The page you are looking for does not exist.</p>
      <Button to="/">Go to the homepage</Button>
    </section>
  );
}
