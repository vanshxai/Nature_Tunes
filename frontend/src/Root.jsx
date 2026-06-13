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
  return (
    <>
      <TopNav />
      <Routes>
        <Route path="/" element={<LibraryPage />} />
        <Route path="/composer" element={<App />} />
      </Routes>
    </>
  );
}
