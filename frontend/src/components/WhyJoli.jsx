import { asset } from "../assets";
import Img from "./Img";

const ITEMS = [
  { label: "On Demand / Scheduled", icon: "why-calendar", glyph: "📅" },
  { label: "Verified Partners", icon: "why-card", glyph: "✔️" },
  { label: "Service Warranty", icon: "why-shield", glyph: "🛡️" },
  { label: "Transparent Pricing", icon: "why-tag", glyph: "🏷️" },
  { label: "Online Payments", icon: "why-card", glyph: "💳" },
  { label: "Support", icon: "why-support", glyph: "🎧" },
];

export default function WhyJoli() {
  return (
    <section className="why" aria-labelledby="why-title">
      <div className="page">
        <h2 id="why-title">WHY JOLI?</h2>
        <ul className="why__list">
          {ITEMS.map((item) => (
            <li key={item.label} className="why__item">
              <span className="why__icon">
                <Img
                  src={asset("why-ball")}
                  className="ball"
                  fallback={<span className="why__fallback" aria-hidden="true">{item.glyph}</span>}
                />
                <Img src={asset(item.icon)} className="glyph" />
              </span>
              {item.label}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
