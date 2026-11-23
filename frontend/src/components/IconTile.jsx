import { Link } from "react-router-dom";
import { categoryIconUrl, initialOf } from "../utils/categories";

/** A category tile: artwork (or the first letter) above an upper-case label. */
export function CategoryTile({ category, to, selected = false }) {
  const url = categoryIconUrl(category);
  return (
    <Link to={to} className={`icon-tile ${selected ? "icon-tile--selected" : ""}`} aria-current={selected ? "true" : undefined}>
      {url ? <img className="icon-tile__image" src={url} alt="" /> : <span className="icon-fallback" aria-hidden="true">{initialOf(category)}</span>}
      <span>{category.name}</span>
    </Link>
  );
}

/** A service tile: its photo from the API, or the first letter. */
export function ServiceTile({ service, to }) {
  return (
    <Link to={to} className="icon-tile">
      {service.image ? <img className="icon-tile__image" src={service.image} alt="" /> : <span className="icon-fallback" aria-hidden="true">{service.name.slice(0, 1).toUpperCase()}</span>}
      <span>{service.name}</span>
    </Link>
  );
}
