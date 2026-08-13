import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { disconnect } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/cases" className="app-title">
          RegTech Platform
        </Link>
        <button className="button-secondary" onClick={disconnect}>
          Disconnect
        </button>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
