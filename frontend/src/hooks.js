import { useCallback, useEffect, useState } from "react";
import { listCategories } from "./api/catalog";
import { getErrorMessage } from "./utils/errors";

/** Categories for a city (or all, when no city is chosen). */
export function useCategories(cityId) {
  const [state, setState] = useState({ status: "loading", items: [], error: "" });

  const load = useCallback(() => {
    let cancelled = false;
    setState((s) => ({ ...s, status: "loading", error: "" }));
    listCategories({ city: cityId })
      .then((items) => !cancelled && setState({ status: "ready", items, error: "" }))
      .catch((e) => !cancelled && setState({ status: "error", items: [], error: getErrorMessage(e) }));
    return () => {
      cancelled = true;
    };
  }, [cityId]);

  useEffect(load, [load]);
  return { ...state, reload: load };
}
