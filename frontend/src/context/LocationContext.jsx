
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { listCities } from "../api/catalog";
import { getErrorMessage } from "../utils/errors";
import { LocationContext } from "./locationContext";

const STORAGE_KEY = "joli.cityId";

function readSavedCity() {
  try {
    return localStorage.getItem(STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

async function fetchLocationData() {
  const [all, served] = await Promise.all([
    listCities(),
    listCities({ available: true }),
  ]);

  return { all, served };
}

export function LocationProvider({ children }) {
  const [cities, setCities] = useState([]);
  const [servedIds, setServedIds] = useState(() => new Set());
  const [selectedCityId, setSelectedCityId] = useState(readSavedCity);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);

  const applyLocationData = useCallback(({ all, served }) => {
    setCities(all);
    setServedIds(new Set(served.map((city) => String(city.id))));

    setSelectedCityId((current) =>
      all.some((city) => String(city.id) === String(current))
        ? current
        : ""
    );

    setStatus("ready");
    setError("");
  }, []);

  // Load cities when the provider mounts.
  useEffect(() => {
    let cancelled = false;

    fetchLocationData()
      .then((data) => {
        if (!cancelled) {
          applyLocationData(data);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(getErrorMessage(e));
          setStatus("error");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [applyLocationData]);

  // Manually reload cities.
  const reload = useCallback(() => {
    setStatus("loading");
    setError("");

    fetchLocationData()
      .then(applyLocationData)
      .catch((e) => {
        setError(getErrorMessage(e));
        setStatus("error");
      });
  }, [applyLocationData]);

  const selectCity = useCallback((id) => {
    const value = id ? String(id) : "";

    setSelectedCityId(value);

    try {
      if (value) {
        localStorage.setItem(STORAGE_KEY, value);
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // The choice won't survive a reload if storage is blocked.
    }
  }, []);

  const openPicker = useCallback(() => {
    setPickerOpen(true);
  }, []);

  const closePicker = useCallback(() => {
    setPickerOpen(false);
  }, []);

  const selectedCity =
    cities.find((city) => String(city.id) === String(selectedCityId)) ?? null;

  const value = useMemo(
    () => ({
      cities,
      servedIds,
      selectedCity,
      selectedCityId,
      selectCity,
      status,
      error,
      reload,
      pickerOpen,
      openPicker,
      closePicker,
    }),
    [
      cities,
      servedIds,
      selectedCity,
      selectedCityId,
      selectCity,
      status,
      error,
      reload,
      pickerOpen,
      openPicker,
      closePicker,
    ]
  );

  return (
    <LocationContext.Provider value={value}>
      {children}
    </LocationContext.Provider>
  );
}
