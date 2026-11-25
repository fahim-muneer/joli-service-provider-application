import { asset } from "../assets";
import { useLocation } from "../context/useLocation";
import Img from "./Img";
import { ChevronDown } from "./Icons";

/** The yellow "Your Location" button; shows the chosen city and opens the popup. */
export default function LocationButton({ onClick }) {
  const { selectedCity, openPicker } = useLocation();
  return (
    <button
      type="button"
      className={`location-btn ${selectedCity ? "has-city" : ""}`}
      aria-haspopup="dialog"
      onClick={() => {
        openPicker();
        onClick?.();
      }}
    >
      {selectedCity ? selectedCity.name : "Your Location"}
      <span className="location-btn__chevron">
        <Img src={asset("chevron-down")} fallback={<ChevronDown />} />
      </span>
    </button>
  );
}
