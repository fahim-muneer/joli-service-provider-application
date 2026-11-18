import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listServices } from "../api/catalog";
import Button from "../components/Button";
import ErrorMessage from "../components/ErrorMessage";
import { CategoryTile, ServiceTile } from "../components/IconTile";
import Spinner from "../components/Spinner";
import { useLocation } from "../context/LocationContext";
import { useCategories } from "../hooks";
import { getErrorMessage } from "../utils/errors";

const PAGE_SIZE = 24;

/** "Service Categories": a row of categories (the chosen one highlighted) and, under it,
 *  the services in that category. ?category=<slug>  ?search=<text>  (city comes from the header). */
export default function Services() {
  const [params] = useSearchParams();
  const category = params.get("category") ?? "";
  const search = params.get("search") ?? "";
  const { selectedCity, selectedCityId } = useLocation();
  const categories = useCategories(selectedCityId);

  const [state, setState] = useState({ status: "loading", items: [], next: false, page: 1, error: "", more: false });

  const fetchPage = useCallback(
    (page) =>
      listServices({ category, city: selectedCityId, search, page, pageSize: PAGE_SIZE }),
    [category, selectedCityId, search],
  );

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading", items: [], next: false, page: 1, error: "", more: false });
    fetchPage(1)
      .then((data) => !cancelled && setState({ status: "ready", items: data.results, next: Boolean(data.next), page: 1, error: "", more: false }))
      .catch((e) => !cancelled && setState((s) => ({ ...s, status: "error", error: getErrorMessage(e) })));
    return () => {
      cancelled = true;
    };
  }, [fetchPage]);

  async function loadMore() {
    setState((s) => ({ ...s, more: true }));
    try {
      const data = await fetchPage(state.page + 1);
      setState((s) => ({ ...s, items: [...s.items, ...data.results], next: Boolean(data.next), page: s.page + 1, more: false }));
    } catch (e) {
      setState((s) => ({ ...s, more: false, error: getErrorMessage(e) }));
    }
  }

  const cityQuery = selectedCityId ? `&city=${selectedCityId}` : "";

  return (
    <section className="page services-page" aria-labelledby="services-title">
      <h1 id="services-title">Service Categories</h1>

      <div className="category-row" role="navigation" aria-label="Categories">
        <Link to="/services" className={`icon-tile ${!category ? "icon-tile--selected" : ""}`} aria-current={!category ? "true" : undefined}>
          <span className="icon-fallback" aria-hidden="true">▦</span>
          <span>All service</span>
        </Link>
        {categories.items.map((c) => (
          <CategoryTile key={c.id} category={c} to={`/services?category=${c.slug}${cityQuery}`} selected={c.slug === category} />
        ))}
      </div>

      {search && <p className="empty">Results for “{search}”{selectedCity ? ` in ${selectedCity.name}` : ""}</p>}

      {state.status === "loading" && <Spinner label="Loading services…" />}
      {state.status === "error" && <ErrorMessage message={state.error} onRetry={() => setState((s) => ({ ...s }))} />}
      {state.status === "ready" && state.items.length === 0 && (
        <p className="empty">
          {selectedCity ? `No services found in ${selectedCity.name}.` : "No services found."}
        </p>
      )}
      {state.status === "ready" && state.items.length > 0 && (
        <div className="service-tiles">
          {state.items.map((service) => (
            <ServiceTile key={service.id} service={service} to={`/services/${service.id}`} />
          ))}
        </div>
      )}
      {state.next && (
        <Button className="load-more" variant="ghost" onClick={loadMore} disabled={state.more}>
          {state.more ? "Loading…" : "Load more"}
        </Button>
      )}
    </section>
  );
}
