import { Link } from "react-router-dom";
import WhyJoli from "./WhyJoli";

const LINKS = [
  ["About Us", "/about"],
  ["Terms & Conditions", "/terms"],
  ["Privacy Policy", "/privacy"],
  ["Cancellation Policy", "/cancellation-policy"],
  ["FAQ", "/faq"],
  ["Blog", "/blog"],
  ["Services", "/services"],
  ["Shopping", "/shopping"],
  ["Joboy Rewards", "/rewards"],
  ["Contact", "/contact"],
];

export default function Footer() {
  return (
    <>
      <WhyJoli />
      <footer className="footer">
        <div className="page">
          <div className="footer__panel">
            <ul className="footer__links">
              {LINKS.map(([label, to]) => (
                <li key={label}><Link to={to}>{label}</Link></li>
              ))}
            </ul>
            <div className="footer__body">
              <strong className="footer__logo">Joli</strong>
              <p className="footer__about">
                Joli connects you to experts around you for Home Maintenance and Repairs, Utility, Lifestyle, Health,
                Beauty, Travel, and other local services, and also brings Local Shopping, Deals, and Events to you,
                right where you are, through an easy to use platform. Schedule services as per your convenience, pay
                online or by cash, get warranty on services, and avail cashbacks and discounts through our rewards
                program. Uncomplicate Life!
              </p>
              <div className="footer__follow">Follow Us</div>
            </div>
          </div>
        </div>
      </footer>
    </>
  );
}
