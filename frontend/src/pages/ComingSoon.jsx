import Button from "../components/Button";

export default function ComingSoon({ title, note }) {
  return (
    <section className="narrow empty-page">
      <h1>{title}</h1>
      <p>{note ?? "This page is coming soon."}</p>
      <Button to="/" variant="ghost">Back to home</Button>
    </section>
  );
}
