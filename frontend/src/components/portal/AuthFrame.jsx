import { Outlet } from "react-router-dom";

/** The bare frame for the provider / admin login, register and verify pages:
 *  a centred white card on the portal's background (Figma: "login page", "number verification"). */
export default function AuthFrame({ portal }) {
  return (
    <div className={`portal portal--${portal} auth`}>
      <main id="content" className="auth__main">
        {portal === "provider" && <div className="auth__logo" aria-label="Joli">Joli</div>}
        <div className="auth__card">
          {portal === "admin" && <div className="auth__welcome">Welcome back admin</div>}
          <Outlet />
        </div>
        {portal === "provider" && (
          <div className="auth__pitch">
            <strong>Join Largest Service Network</strong>
            <ul>
              <li>Increase Your Earnings</li>
              <li>Improve Productivity</li>
              <li>Large Customer Base</li>
            </ul>
          </div>
        )}
      </main>
    </div>
  );
}
