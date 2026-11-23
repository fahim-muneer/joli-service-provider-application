import { Outlet } from "react-router-dom";
import Footer from "./Footer";
import Header from "./Header";
import LocationModal from "./LocationModal";

export default function Layout() {
  return (
    <div className="app">
      <a href="#content" className="skip-link">Skip to content</a>
      <Header />
      <main id="content" className="main">
        <Outlet />
      </main>
      <Footer />
      <LocationModal />
    </div>
  );
}
