/** Placeholder for portal screens that are in the design but not built yet (inside the portal frame).
 *  `heading` is only for the admin portal; the provider frame already shows the page title. */
export default function PortalSoon({ heading, note }) {
  return (
    <>
      {heading && <div className="page-head"><h1>{heading}</h1></div>}
      <div className="panel"><p className="muted">{note ?? "Coming soon."}</p></div>
    </>
  );
}
