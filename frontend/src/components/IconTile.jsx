
import { Link } from "react-router-dom";
import {
  Wrench,
  Sparkles,
  Droplets,
  Zap,
  Paintbrush,
  Snowflake,
  Sprout,
  CarFront,
  House,
  Sofa,
  WashingMachine,
  Hammer,
  Truck,
  Scissors,
  ShieldCheck,
  Plug,
} from "lucide-react";

import { categoryIconUrl, initialOf } from "../utils/categories";

// Keep these names synchronized with the Admin Category icon picker.
const ICON_MAP = {
  Wrench,
  Sparkles,
  Droplets,
  Zap,
  Paintbrush,
  Snowflake,
  Sprout,
  CarFront,
  House,
  Sofa,
  WashingMachine,
  Hammer,
  Truck,
  Scissors,
  ShieldCheck,
  Plug,
};

/** A category tile: Lucide icon, existing artwork, or first letter. */
export function CategoryTile({ category, to, selected = false }) {
  const Icon = ICON_MAP[category.icon];
  const url = categoryIconUrl(category);

  return (
    <Link
      to={to}
      className={`icon-tile ${selected ? "icon-tile--selected" : ""}`}
      aria-current={selected ? "true" : undefined}
    >
      {Icon ? (
        <span className="icon-tile__icon" aria-hidden="true">
          <Icon size={32} strokeWidth={1.8} />
        </span>
      ) : url ? (
        <img className="icon-tile__image" src={url} alt="" />
      ) : (
        <span className="icon-fallback" aria-hidden="true">
          {initialOf(category)}
        </span>
      )}

      <span>{category.name}</span>
    </Link>
  );
}

/** A service tile: its photo from the API, or the first letter. */
export function ServiceTile({ service, to }) {
  return (
    <Link to={to} className="icon-tile">
      {service.image ? (
        <img
          className="icon-tile__image"
          src={service.image}
          alt=""
        />
      ) : (
        <span className="icon-fallback" aria-hidden="true">
          {service.name.slice(0, 1).toUpperCase()}
        </span>
      )}

      <span>{service.name}</span>
    </Link>
  );
}
