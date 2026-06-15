import { useEffect } from 'react';
import { Routes, Route, NavLink, useLocation, useNavigate } from 'react-router-dom';
import App from './App.jsx';
import LibraryPage from './pages/LibraryPage.jsx';
import LandingPage from './pages/LandingPage.jsx';
import ListenPage from './pages/ListenPage.jsx';
import AdminPage from './pages/AdminPage.jsx';

// Internal nav shown only on /library and /composer (admin tool routes)
function TopNav() {
  return (
    <nav className="topnav">
      <div className="topnav-brand">🌿 NatureTunes</div>
      <div className="topnav-links">
        <NavLink to="/library" className={({ isActive }) => 'topnav-link' + (isActive ? ' active' : '')}>
          Library
        </NavLink>
        <NavLink to="/composer" className={({ isActive }) => 'topnav-link' + (isActive ? ' active' : '')}>
          Composer
        </NavLink>
      </div>
    </nav>
  );
}

export default function Root() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const navEntry = performance.getEntriesByType?.('navigation')?.[0];
    const isReload = navEntry?.type === 'reload';

    if (isReload && location.pathname !== '/') {
      navigate('/', { replace: true });
    }
  }, [location.pathname, navigate]);

  return (
    <Routes>
      <Route path="/"         element={<LandingPage />} />
      <Route path="/listen"   element={<ListenPage />} />
      <Route path="/admin"    element={<AdminPage />} />
      <Route path="/library"  element={<><TopNav /><LibraryPage /></>} />
      <Route path="/composer" element={<><TopNav /><App /></>} />
    </Routes>
  );
}
