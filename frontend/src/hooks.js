
import { useCallback, useEffect, useState } from "react";
import { listCategories } from "./api/catalog";
import { getErrorMessage } from "./utils/errors";

/** Categories for a city (or all, when no city is chosen). */
export function useCategories(cityId) {
  const [state, setState] = useState({
    status: "loading",
    items: [],
    error: "",
  });

  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;

    listCategories({ city: cityId })
      .then((items) => {
        if (!cancelled) {
          setState({
            status: "ready",
            items,
            error: "",
          });
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setState({
            status: "error",
            items: [],
            error: getErrorMessage(e),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [cityId, attempt]);

  const reload = useCallback(() => {
    setState((current) => ({
      ...current,
      status: "loading",
      error: "",
    }));

    setAttempt((current) => current + 1);
  }, []);

  return { ...state, reload };
}

/**
 * Load something once (and again when `deps` change or `reload()` is called).
 *
 * Returns:
 * {
 *   status: "loading" | "ready" | "error",
 *   data,
 *   error,
 *   reload,
 *   setData
 * }
 *
 * setData lets a page show a server reply without flashing the spinner.
 */
export function useLoad(fetcher, deps = []) {
  const [state, setState] = useState({
    status: "loading",
    data: null,
    error: "",
  });

  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;

    fetcher()
      .then((data) => {
        if (!cancelled) {
          setState({
            status: "ready",
            data,
            error: "",
          });
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setState({
            status: "error",
            data: null,
            error: getErrorMessage(e),
          });
        }
      });

    return () => {
      cancelled = true;
    };

    // The caller controls when this hook should reload through deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);

  const reload = useCallback(() => {
    setState((current) => ({
      ...current,
      status: "loading",
      error: "",
    }));

    setAttempt((current) => current + 1);
  }, []);

  const setData = useCallback((data) => {
    setState((current) => ({
      ...current,
      data,
    }));
  }, []);

  return { ...state, reload, setData };
}
