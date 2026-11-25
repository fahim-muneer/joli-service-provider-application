import { api } from "./client";
import { clean } from "./params";

// Admin portal: /providers/admin/...
const data = (promise) => promise.then((r) => r.data);

/** Paginated { count, next, previous, results }. status: pending | under_review | approved | rejected | suspended */
export const listProviders = ({ status, search, page, pageSize } = {}) =>
  data(api.get("/providers/admin/providers/", { params: clean({ status, search, page, page_size: pageSize }) }));
export const getProvider = (id) => data(api.get(`/providers/admin/providers/${id}/`));

// Every action answers with the provider's fresh detail.
export const approveProvider = (id, note = "") => data(api.post(`/providers/admin/providers/${id}/approve/`, { note }));
export const rejectProvider = (id, reason) => data(api.post(`/providers/admin/providers/${id}/reject/`, { reason }));
export const suspendProvider = (id, reason) => data(api.post(`/providers/admin/providers/${id}/suspend/`, { reason }));
export const reinstateProvider = (id, note = "") => data(api.post(`/providers/admin/providers/${id}/reinstate/`, { note }));

/** decision: "approved" | "rejected" (a reason is required to reject). */
export const reviewDocument = (id, { decision, reason = "", remark = "" }) =>
  data(api.post(`/providers/admin/documents/${id}/review/`, { decision, reason, remark }));


// ------------------------- Category management -------------------------

/** Paginated category list. isActive: true | false | undefined */
export const listAdminCategories = ({
  search,
  isActive,
  page,
  pageSize,
} = {}) =>
  data(
    api.get("/services/admin/categories/", {
      params: clean({
        search,
        is_active: isActive,
        page,
        page_size: pageSize,
      }),
    }),
  );

export const createCategory = (payload) =>
  data(api.post("/services/admin/categories/", payload));

export const updateCategory = (id, payload) =>
  data(api.patch(`/services/admin/categories/${id}/`, payload));

export const archiveCategory = (id) =>
  data(api.delete(`/services/admin/categories/${id}/`));
