import { Link } from "react-router-dom";
import { asset } from "../assets";
import ErrorMessage from "../components/ErrorMessage";
import Img from "../components/Img";
import { CategoryTile } from "../components/IconTile";
import PartnerLink from "../components/PartnerLink";
import Spinner from "../components/Spinner";
import { useLocation } from "../context/LocationContext";
import { useCategories } from "../hooks";
import { categoryBannerUrl } from "../utils/categories";

const PARTNER_POINTS = [
  { icon: "partner-productivity", title: "Increase Your Earnings", text: "With Joli, you do more than your usual jobs, and earn more. No more bargaining with your customers!" },
  { icon: "partner-earnings", title: "Increase Your Earnings", text: "With Joli, you do more than your usual jobs, and earn more. No more bargaining with your customers!" },
  { icon: "partner-customers", title: "Large Customer Base", text: "With us, you are visible to a much larger customer base, without any marketing costs. We do your marketing for you!" },
];

const MAX_TILES = 13; // 7 x 2 grid, the last place is "More service"

function MostUsedServices() {
  const { selectedCity, selectedCityId } = useLocation();
  const { status, items, error, reload } = useCategories(selectedCityId);
  const query = selectedCityId ? `&city=${selectedCityId}` : "";

  if (status === "loading") return <Spinner label="Loading services…" />;
  if (status === "error") return <ErrorMessage message={error} onRetry={reload} />;
  if (items.length === 0) {
    return (
      <p className="empty">
        {selectedCity ? `No services are available in ${selectedCity.name} yet. Try another city.` : "No services yet. Please check back soon."}
      </p>
    );
  }

  const banners = items.filter((c) => categoryBannerUrl(c)).slice(0, 4);
  return (
    <>
      {banners.length > 0 && (
        <div className="banners">
          {banners.map((category) => (
            <Link key={category.id} className="banner" to={`/services?category=${category.slug}${query}`}>
              <img className="banner__image" src={categoryBannerUrl(category)} alt="" />
              <span>{category.name} service</span>
            </Link>
          ))}
        </div>
      )}
      <div className="icon-grid">
        {items.slice(0, MAX_TILES).map((category) => (
          <CategoryTile key={category.id} category={category} to={`/services?category=${category.slug}${query}`} />
        ))}
        <Link to="/services" className="icon-tile">
          <Img src={asset("icon-more")} className="icon-tile__image" fallback={<span className="icon-fallback" aria-hidden="true">»</span>} />
          <span>More service</span>
        </Link>
      </div>
    </>
  );
}

export default function Home() {
  return (
    <>
      <section className="page section" aria-labelledby="most-used">
        <h2 id="most-used" className="section-title">Most Used Services</h2>
        <MostUsedServices />
      </section>

      <section className="partner" aria-labelledby="partner-title">
        <div className="page partner__inner">
          <div>
            <div className="partner__cta">
              <h2 id="partner-title">
                Are you a service expert?
                <span>Join worlds Largest Service Network</span>
              </h2>
              <PartnerLink size="large">Register as a partner</PartnerLink>
            </div>
            <ul className="partner__list">
              {PARTNER_POINTS.map((point, index) => (
                <li key={index} className="partner__item">
                  <Img src={asset(point.icon)} fallback={<span className="badge" aria-hidden="true" />} />
                  <div>
                    <strong>{point.title}</strong>
                    <span>{point.text}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <Img src={asset("partner-workers")} className="partner__image" />
        </div>
      </section>
    </>
  );
}
