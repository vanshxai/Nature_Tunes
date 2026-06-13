import { Routes, Route, NavLink } from 'react-router-dom';
import App from './App.jsx';
import LibraryPage from './pages/LibraryPage.jsx';

// Slim global navigation sitting above both pages.
function TopNav() {
  return (
    <nav className="topnav">
      <div className="topnav-brand">🌿 NatureTunes</div>
      <div className="topnav-links">
        <NavLink to="/" end className={({ isActive }) => 'topnav-link' + (isActive ? ' active' : '')}>
          Composer
        </NavLink>
        <NavLink to="/library" className={({ isActive }) => 'topnav-link' + (isActive ? ' active' : '')}>
          Library
        </NavLink>
      </div>
    </nav>
  );
}

export default function Root() {
  return (
    <>
      <TopNav />
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/library" element={<LibraryPage />} />
      </Routes>
    </>
  );
}
