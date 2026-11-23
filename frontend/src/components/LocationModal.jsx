import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "../context/LocationContext";
import { CityIcon } from "./Icons";
import Spinner from "./Spinner";
import ErrorMessage from "./ErrorMessage";

/** "Select Your location to continue": tiles for cities where Joli is live, and a
 *  dropdown for every other city. Uses the native <dialog> (focus trap, Esc, backdrop). */
export default function LocationModal() {
  const { cities, servedIds, selectedCityId, selectCity, status, error, reload, pickerOpen, closePicker } = useLocation();
  const dialogRef = useRef(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || typeof dialog.showModal !== "function") return;
    if (pickerOpen && !dialog.open) dialog.showModal();
    if (!pickerOpen && dialog.open) dialog.close();
  }, [pickerOpen]);

  const match = (city) => city.name.toLowerCase().includes(filter.trim().toLowerCase());
  const served = useMemo(() => cities.filter((c) => servedIds.has(String(c.id)) && match(c)), [cities, servedIds, filter]);
  const others = useMemo(() => cities.filter((c) => !servedIds.has(String(c.id)) && match(c)), [cities, servedIds, filter]);

  function choose(id) {
    selectCity(id);
    setFilter("");
    closePicker();
  }

  return (
    <dialog
      ref={dialogRef}
      className="location-modal"
      aria-labelledby="location-title"
      onClose={closePicker}
      onClick={(e) => e.target === dialogRef.current && closePicker()}
    >
      <div className="location-modal__inner">
        <button type="button" className="location-modal__close" aria-label="Close" onClick={closePicker}>✕</button>
        <h2 id="location-title">Select Your location to continue</h2>
        <label className="visually-hidden" htmlFor="city-filter">Search for a city</label>
        <input id="city-filter" className="location-modal__search" type="search" placeholder="Search for your city" value={filter} onChange={(e) => setFilter(e.target.value)} />

        {status === "loading" && <Spinner label="Loading cities…" />}
        {status === "error" && <ErrorMessage message={error} onRetry={reload} />}

        {status === "ready" && (
          <>
            <h3>Service available cities</h3>
            {served.length === 0 ? (
              <p className="empty">{filter ? "No matching city." : "We are not live in any city yet."}</p>
            ) : (
              <ul className="city-grid">
                {served.map((city) => (
                  <li key={city.id}>
                    <button type="button" className={`city-tile ${String(city.id) === String(selectedCityId) ? "is-selected" : ""}`} onClick={() => choose(city.id)}>
                      <CityIcon />
                      {city.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {others.length > 0 && (
              <>
                <h3>Your City not listed? Select Here</h3>
                <label className="visually-hidden" htmlFor="other-city">Other cities</label>
                <select id="other-city" value="" onChange={(e) => e.target.value && choose(e.target.value)}>
                  <option value="">Choose</option>
                  {others.map((city) => (
                    <option key={city.id} value={city.id}>{city.name}</option>
                  ))}
                </select>
              </>
            )}
          </>
        )}
      </div>
    </dialog>
  );
}
