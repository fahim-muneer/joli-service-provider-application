import { useMemo, useState } from "react";
import { addSchedule, deleteSchedule, listSchedule } from "../../api/provider";
import Button from "../../components/Button";
import ErrorMessage from "../../components/ErrorMessage";
import { useLoad } from "../../hooks";
import { getErrorMessage } from "../../utils/errors";

const pad = (n) => String(n).padStart(2, "0");
const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** Every date from `from` to `to` (or just `from`). The backend accepts at most 62 at once. */
function datesBetween(from, to) {
  const out = [];
  const day = new Date(`${from}T00:00:00`);
  const end = new Date(`${to || from}T00:00:00`);
  while (day <= end && out.length < 63) {
    out.push(iso(day));
    day.setDate(day.getDate() + 1);
  }
  return out;
}

const longDay = (value) => new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });

// Figma "Schedule page": a month calendar on the left, the chosen day on the right.
// The design shows bookings there; until bookings exist it shows the hours the provider is available.
export default function Schedule() {
  const todayIso = iso(new Date());
  const [month, setMonth] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const [selected, setSelected] = useState(todayIso);
  const [form, setForm] = useState({ to: "", start_time: "09:00", end_time: "17:00", is_available: "true" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const first = iso(month);
  const last = iso(new Date(month.getFullYear(), month.getMonth() + 1, 0));
  const windows = useLoad(() => listSchedule({ from: first, to: last }), [first]);

  const byDay = useMemo(() => {
    const map = {};
    for (const w of windows.data ?? []) (map[w.date] ??= []).push(w);
    return map;
  }, [windows.data]);

  const cells = [];
  for (let i = 0; i < month.getDay(); i += 1) cells.push(null);
  for (let d = 1; d <= new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate(); d += 1) cells.push(iso(new Date(month.getFullYear(), month.getMonth(), d)));

  const move = (delta) => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + delta, 1));
  const goToday = () => { const d = new Date(); setMonth(new Date(d.getFullYear(), d.getMonth(), 1)); setSelected(todayIso); };
  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  const isPast = selected < todayIso;
  const dayWindows = byDay[selected] ?? [];

  async function handleAdd(e) {
    e.preventDefault();
    setError("");
    const dates = datesBetween(selected, form.to);
    if (dates.length > 62) {
      setError("Pick at most 62 days at a time.");
      return;
    }
    setBusy(true);
    try {
      await addSchedule({ dates, start_time: form.start_time, end_time: form.end_time, is_available: form.is_available === "true" });
      windows.reload();
      setForm((f) => ({ ...f, to: "" }));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    setError("");
    try {
      await deleteSchedule(id);
      windows.reload();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div className="sched">
      <div className="panel cal">
        <div className="cal__head">
          <Button variant="ghost" size="small" onClick={() => move(-1)} aria-label="Previous month">‹</Button>
          <Button variant="ghost" size="small" onClick={() => move(1)} aria-label="Next month">›</Button>
          <strong>{month.toLocaleDateString("en-IN", { month: "long", year: "numeric" })}</strong>
          <Button variant="ghost" size="small" onClick={goToday}>Today</Button>
        </div>
        <div className="cal__grid" role="grid">
          {DOW.map((d) => <div key={d} className="cal__dow" role="columnheader">{d}</div>)}
          {cells.map((day, i) => {
            if (!day) return <div key={`b${i}`} className="cal__day cal__day--blank" />;
            const list = byDay[day] ?? [];
            const cls = ["cal__day", day === todayIso && "cal__day--today", day === selected && "cal__day--sel"].filter(Boolean).join(" ");
            return (
              <button key={day} type="button" className={cls} aria-pressed={day === selected} onClick={() => setSelected(day)}>
                <span className="cal__num">{Number(day.slice(8))}</span>
                {list.length > 0 && (
                  <span className="cal__dots" aria-label={`${list.length} windows`}>
                    {list.slice(0, 3).map((w) => <i key={w.id} className={`cal__dot ${w.is_available ? "" : "cal__dot--off"}`} />)}
                  </span>
                )}
                {list.length > 1 && <span className="cal__tag">{list.length} windows</span>}
              </button>
            );
          })}
        </div>
        <div className="cal__legend">
          <span><i style={{ background: "#2563eb" }} />Available</span>
          <span><i style={{ background: "#f59e0b" }} />Blocked</span>
        </div>
        {windows.status === "error" && <ErrorMessage message={windows.error} onRetry={windows.reload} />}
      </div>

      <div className="panel">
        <h2>{longDay(selected)}</h2>
        {dayWindows.length === 0 && <p className="muted">Nothing set for this day.</p>}
        {dayWindows.map((w) => (
          <div key={w.id} className="slot">
            <div><strong>{w.start_time.slice(0, 5)} – {w.end_time.slice(0, 5)}</strong></div>
            <span className={`status status--${w.is_available ? "ok" : "bad"}`}>{w.is_available ? "Available" : "Blocked"}</span>
            {!isPast && <Button variant="ghost" size="small" onClick={() => remove(w.id)}>Delete</Button>}
          </div>
        ))}

        {isPast ? <p className="muted">This day has passed.</p> : (
          <form className="form" onSubmit={handleAdd}>
            <label>Start<input type="time" value={form.start_time} onChange={update("start_time")} required /></label>
            <label>End<input type="time" value={form.end_time} onChange={update("end_time")} required /></label>
            <label>
              Type
              <select value={form.is_available} onChange={update("is_available")}>
                <option value="true">Available</option>
                <option value="false">Blocked (for example lunch)</option>
              </select>
            </label>
            <label>Repeat every day until (optional)<input type="date" min={selected} value={form.to} onChange={update("to")} /></label>
            <ErrorMessage message={error} />
            <Button type="submit" disabled={busy}>{busy ? "Adding…" : "Add window"}</Button>
          </form>
        )}
      </div>
    </div>
  );
}
