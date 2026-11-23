import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { listCities } from "../api/catalog";
import { getErrorMessage } from "../utils/errors";

const LocationContext = createContext(null);
const STORAGE_KEY = "joli.cityId";

function readSavedCity() {
  try {
    return localStorage.getItem(STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

/** The city the customer is browsing in, plus the "Select your location" popup.
 *  The saved city is re-validated against the server's list (an admin can switch a city off). */
export function LocationProvider({ children }) {
  const [cities, setCities] = useState([]);
  const [servedIds, setServedIds] = useState(() => new Set()); // cities where a provider is live
  const [selectedCityId, setSelectedCityId] = useState(readSavedCity);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);

  const load = useCallback(() => {
    setStatus("loading");
    Promise.all([listCities(), listCities({ available: true })])
      .then(([all, served]) => {
        setCities(all);
        setServedIds(new Set(served.map((c) => String(c.id))));
        setSelectedCityId((current) => (all.some((c) => String(c.id) === String(current)) ? current : ""));
        setStatus("ready");
      })
      .catch((e) => {
        setError(getErrorMessage(e));
        setStatus("error");
      });
  }, []);

  useEffect(load, [load]);

  const selectCity = useCallback((id) => {
    const value = id ? String(id) : "";
    setSelectedCityId(value);
    try {
      if (value) localStorage.setItem(STORAGE_KEY, value);
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage blocked: the choice just won't survive a reload */
    }
  }, []);

  const openPicker = useCallback(() => setPickerOpen(true), []);
  const closePicker = useCallback(() => setPickerOpen(false), []);

  const selectedCity = cities.find((c) => String(c.id) === String(selectedCityId)) ?? null;
  const value = useMemo(
    () => ({
      cities, servedIds, selectedCity, selectedCityId, selectCity,
      status, error, reload: load, pickerOpen, openPicker, closePicker,
    }),
    [cities, servedIds, selectedCity, selectedCityId, selectCity, status, error, load, pickerOpen, openPicker, closePicker],
  );
  return <LocationContext.Provider value={value}>{children}</LocationContext.Provider>;
}

export function useLocation() {
  const context = useContext(LocationContext);
  if (!context) throw new Error("useLocation must be used inside <LocationProvider>");
  return context;
}
