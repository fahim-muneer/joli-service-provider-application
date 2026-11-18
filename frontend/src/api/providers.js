import { api } from "./client";
import { clean } from "./params";

/** Who can do this job? Paginated { count, next, previous, results }.
 *  scheduledAt: an ISO date-time with offset, e.g. new Date(...).toISOString():
 *  only providers who are free then are returned.
 *  ordering: "price" | "-price" | "experience" | "-experience". */
export const listServiceProviders = (
  serviceId,
  { city, area, scheduledAt, ordering, page, pageSize } = {},
) =>
  api
    .get(`/services/${serviceId}/providers/`, {
      params: clean({ city, area, scheduled_at: scheduledAt, ordering, page, page_size: pageSize }),
    })
    .then((r) => r.data);

export const getPublicProvider = (id) => api.get(`/providers/public/${id}/`).then((r) => r.data);
