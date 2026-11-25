
import { useState } from "react";
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
  Check,
} from "lucide-react";

import {
  listAdminCategories,
  createCategory,
  updateCategory,
  archiveCategory,
} from "../../api/admin";

import Button from "../../components/Button";
import ErrorMessage from "../../components/ErrorMessage";
import Spinner from "../../components/Spinner";
import { useLoad } from "../../hooks";
import { formatDate } from "../../utils/status";

// Icon names are stored in the database.
const CATEGORY_ICONS = [
  { name: "Wrench", component: Wrench, label: "Repair" },
  { name: "Sparkles", component: Sparkles, label: "Cleaning" },
  { name: "Droplets", component: Droplets, label: "Plumbing" },
  { name: "Zap", component: Zap, label: "Electrical" },
  { name: "Paintbrush", component: Paintbrush, label: "Painting" },
  { name: "Snowflake", component: Snowflake, label: "AC Service" },
  { name: "Sprout", component: Sprout, label: "Garden" },
  { name: "CarFront", component: CarFront, label: "Car Service" },
  { name: "House", component: House, label: "Home" },
  { name: "Sofa", component: Sofa, label: "Furniture" },
  { name: "WashingMachine", component: WashingMachine, label: "Laundry" },
  { name: "Hammer", component: Hammer, label: "Construction" },
  { name: "Truck", component: Truck, label: "Moving" },
  { name: "Scissors", component: Scissors, label: "Salon" },
  { name: "ShieldCheck", component: ShieldCheck, label: "Security" },
  { name: "Plug", component: Plug, label: "Appliances" },
];

const ICON_MAP = Object.fromEntries(
  CATEGORY_ICONS.map((item) => [item.name, item.component]),
);

const TABS = [
  ["", "All"],
  ["true", "Active"],
  ["false", "Archived"],
];

const EMPTY_FORM = {
  name: "",
  icon: "",
  description: "",
  display_order: 0,
  is_active: true,
};

function getErrorMessage(error) {
  const data = error?.response?.data;

  if (!data) return "Something went wrong. Please try again.";
  if (typeof data === "string") return data;

  return Object.entries(data)
    .map(([field, messages]) => {
      const message = Array.isArray(messages)
        ? messages.join(" ")
        : String(messages);
      return `${field}: ${message}`;
    })
    .join(" | ");
}

function CategoryIconPicker({ value, onChange }) {
  const SelectedIcon = ICON_MAP[value];

  return (
    <div>
      <p style={{ marginBottom: 10, fontSize: 14, fontWeight: 600 }}>
        Select Category Icon
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(76px, 1fr))",
          gap: 10,
        }}
      >
        {CATEGORY_ICONS.map(({ name, component: Icon, label }) => {
          const selected = value === name;

          return (
            <button
              key={name}
              type="button"
              onClick={() => onChange(name)}
              aria-pressed={selected}
              title={label}
              style={{
                position: "relative",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 7,
                minHeight: 78,
                padding: 10,
                border: selected
                  ? "2px solid var(--primary, #2563eb)"
                  : "1px solid var(--border, #ddd)",
                borderRadius: 10,
                background: selected
                  ? "var(--surface-secondary, #eff6ff)"
                  : "var(--surface, #fff)",
                color: "inherit",
                cursor: "pointer",
              }}
            >
              <Icon size={23} strokeWidth={1.8} />

              <span style={{ fontSize: 11 }}>{label}</span>

              {selected && (
                <Check
                  size={14}
                  style={{
                    position: "absolute",
                    top: 5,
                    right: 5,
                  }}
                />
              )}
            </button>
          );
        })}
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginTop: 12,
        }}
      >
        <span className="muted">Selected:</span>

        {SelectedIcon ? (
          <>
            <SelectedIcon size={22} />
            <strong>{value}</strong>
          </>
        ) : (
          <span className="muted">
            {value || "No icon selected"}
          </span>
        )}

        {value && (
          <button
            type="button"
            className="btn btn--ghost btn--small"
            onClick={() => onChange("")}
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

export default function Categories() {
  const [active, setActive] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);

  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState("");

  const list = useLoad(
    () =>
      listAdminCategories({
        search: query,
        isActive: active === "" ? undefined : active === "true",
        page,
        pageSize: 20,
      }),
    [active, query, page],
  );

  const pickTab = (value) => {
    setActive(value);
    setPage(1);
  };

  const submitSearch = (e) => {
    e.preventDefault();
    setQuery(search.trim());
    setPage(1);
  };

  const openCreateForm = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setActionError("");
    setShowForm(true);
  };

  const openEditForm = (category) => {
    setEditingId(category.id);
    setForm({
      name: category.name || "",
      icon: category.icon || "",
      description: category.description || "",
      display_order: category.display_order ?? 0,
      is_active: category.is_active,
    });
    setActionError("");
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
    setActionError("");
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;

    setForm((current) => ({
      ...current,
      [name]:
        type === "checkbox"
          ? checked
          : name === "display_order"
            ? value === "" ? "" : Number(value)
            : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setActionError("");

    const payload = {
      ...form,
      display_order: Number(form.display_order || 0),
    };

    try {
      if (editingId) {
        await updateCategory(editingId, payload);
      } else {
        await createCategory(payload);
      }

      closeForm();
      list.reload();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const handleArchive = async (category) => {
    const confirmed = window.confirm(
      `Archive "${category.name}"? It will no longer be active.`,
    );

    if (!confirmed) return;

    setActionError("");

    try {
      await archiveCategory(category.id);
      list.reload();
    } catch (error) {
      setActionError(getErrorMessage(error));
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Categories</h1>
          <p>
            {list.status === "ready"
              ? `${list.data.count} categories`
              : "Manage your service categories"}
          </p>
        </div>

        <Button size="small" onClick={openCreateForm}>
          Add Category
        </Button>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={active === value}
            className={`tab ${active === value ? "tab--on" : ""}`}
            onClick={() => pickTab(value)}
          >
            {label}
          </button>
        ))}
      </div>

      <form className="filters row" onSubmit={submitSearch}>
        <label className="grow">
          Search by category name or description
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search categories..."
          />
        </label>

        <Button type="submit" size="small">
          Search
        </Button>
      </form>

      {showForm && (
        <form className="panel form" onSubmit={handleSubmit}>
          <h2>{editingId ? "Edit Category" : "Create Category"}</h2>

          {actionError && <ErrorMessage message={actionError} />}

          <label>
            Category name *
            <input
              name="name"
              value={form.name}
              onChange={handleChange}
              maxLength={80}
              required
            />
          </label>

          <CategoryIconPicker
            value={form.icon}
            onChange={(icon) =>
              setForm((current) => ({ ...current, icon }))
            }
          />

          <label>
            Description
            <textarea
              name="description"
              value={form.description}
              onChange={handleChange}
              rows={3}
            />
          </label>

          <label>
            Display order
            <input
              name="display_order"
              type="number"
              min="0"
              value={form.display_order}
              onChange={handleChange}
            />
          </label>

          {editingId && (
            <label>
              <input
                name="is_active"
                type="checkbox"
                checked={form.is_active}
                onChange={handleChange}
              />
              Active category
            </label>
          )}

          <div className="row">
            <Button type="submit" size="small" disabled={saving}>
              {saving
                ? "Saving..."
                : editingId
                  ? "Save Changes"
                  : "Create Category"}
            </Button>

            <Button
              type="button"
              variant="ghost"
              size="small"
              onClick={closeForm}
              disabled={saving}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}

      {actionError && !showForm && (
        <ErrorMessage message={actionError} />
      )}

      {list.status === "loading" && (
        <Spinner label="Loading categories..." />
      )}

      {list.status === "error" && (
        <ErrorMessage message={list.error} onRetry={list.reload} />
      )}

      {list.status === "ready" && list.data.results.length === 0 && (
        <p className="empty">No categories found.</p>
      )}

      {list.status === "ready" && list.data.results.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Icon</th>
                <th>Display order</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {list.data.results.map((category) => {
                const Icon = ICON_MAP[category.icon];

                return (
                  <tr key={category.id}>
                    <td>
                      <strong>{category.name}</strong>
                      {category.description && (
                        <small
                          className="muted"
                          style={{ display: "block" }}
                        >
                          {category.description}
                        </small>
                      )}
                    </td>

                    <td>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 7,
                        }}
                      >
                        {Icon && <Icon size={20} />}
                        <span>{category.icon || "—"}</span>
                      </div>
                    </td>

                    <td>{category.display_order}</td>

                    <td>
                      <span
                        className={`status ${
                          category.is_active
                            ? "status--approved"
                            : "status--rejected"
                        }`}
                      >
                        {category.is_active ? "Active" : "Archived"}
                      </span>
                    </td>

                    <td>{formatDate(category.created_at)}</td>

                    <td>
                      <div className="row">
                        <button
                          type="button"
                          className="btn btn--ghost btn--small"
                          onClick={() => openEditForm(category)}
                        >
                          Edit
                        </button>

                        {category.is_active && (
                          <button
                            type="button"
                            className="btn btn--ghost btn--small"
                            onClick={() => handleArchive(category)}
                          >
                            Archive
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {list.status === "ready" &&
        (list.data.previous || list.data.next) && (
          <div className="pager">
            <Button
              variant="ghost"
              size="small"
              disabled={!list.data.previous}
              onClick={() => setPage((current) => current - 1)}
            >
              Previous
            </Button>

            <span>
              Page {page} · {list.data.count} categories
            </span>

            <Button
              variant="ghost"
              size="small"
              disabled={!list.data.next}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </Button>
          </div>
        )}
    </>
  );
}
