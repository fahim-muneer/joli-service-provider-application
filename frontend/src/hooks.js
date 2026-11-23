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

/** Load something once (and again when `deps` change or `reload()` is called).
 *  Returns { status: "loading" | "ready" | "error", data, error, reload, setData }.
 *  setData lets a page show a server reply without flashing the spinner. */
export function useLoad(fetcher, deps = []) {
  const [state, setState] = useState({ status: "loading", data: null, error: "" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, status: "loading", error: "" }));
    fetcher()
      .then((data) => !cancelled && setState({ status: "ready", data, error: "" }))
      .catch((e) => !cancelled && setState({ status: "error", data: null, error: getErrorMessage(e) }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);
  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  const setData = useCallback((data) => setState((s) => ({ ...s, data })), []);
  return { ...state, reload, setData };
}
