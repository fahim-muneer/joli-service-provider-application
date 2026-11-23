import { api } from "./client";
import { clean } from "./params";

export const listCities = ({ available = false } = {}) =>
  api.get("/locations/cities/", { params: clean({ available: available || undefined }) }).then((r) => r.data);

export const listAreas = (cityId) =>
  api.get(`/locations/cities/${cityId}/areas/`).then((r) => r.data);

/** With `city`, only categories that have a service available there. */
export const listCategories = ({ city } = {}) =>
  api.get("/services/categories/", { params: clean({ city }) }).then((r) => r.data);

/** Paginated: resolves to { count, next, previous, results }. */
export const listServices = ({ category, city, search, page, pageSize } = {}) =>
  api
    .get("/services/", { params: clean({ category, city, search, page, page_size: pageSize }) })
    .then((r) => r.data);

export const getService = (id, { city } = {}) =>
  api.get(`/services/${id}/`, { params: clean({ city }) }).then((r) => r.data);
