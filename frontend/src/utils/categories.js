import { asset } from "../assets";

/** The artwork key of a category: its `icon` field, lower-cased ("plumber", "cleaning", ...). */
export const iconKey = (category) => (category?.icon ?? "").trim().toLowerCase();

export const categoryIconUrl = (category) => (iconKey(category) ? asset(`icon-${iconKey(category)}`) : null);
export const categoryBannerUrl = (category) => (iconKey(category) ? asset(`banner-${iconKey(category)}`) : null);

/** A capital letter to show when a category has no artwork. */
export const initialOf = (category) => (category?.name ?? "?").trim().slice(0, 1).toUpperCase();
