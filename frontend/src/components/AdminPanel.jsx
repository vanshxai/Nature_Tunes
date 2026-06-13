import { useState } from 'react';

const ADMIN_PASSWORD = 'admin';
const SESSION_KEY = 'birdmind_admin';

export default function AdminPanel({ manifest, onClose }) {
  const [authed, setAuthed] = useState(
    () => sessionStorage.getItem(SESSION_KEY) === 'true'
  );
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);
  const [shake, setShake] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (password === ADMIN_PASSWORD) {
      sessionStorage.setItem(SESSION_KEY, 'true');
      setAuthed(true);
      setError(false);
    } else {
      setError(true);
      setShake(true);
      setTimeout(() => setShake(false), 400);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem(SESSION_KEY);
    setAuthed(false);
    setPassword('');
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">🔒 Admin</span>
          <button className="modal-close" onClick={onClose} title="Close">✕</button>
        </div>

        {!authed ? (
          <form className="admin-login" onSubmit={handleSubmit}>
            <input
              type="password"
              className={`admin-input ${shake ? 'shake' : ''}`}
              placeholder="Password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(false); }}
              autoFocus
            />
            {error && <span className="admin-error">Incorrect password</span>}
            <button type="submit" className="btn btn-accent">Submit</button>
          </form>
        ) : (
          <div className="admin-dashboard">
            <div className="admin-stats">
              <div className="stat-card">
                <div className="stat-number">{manifest.birds.length}</div>
                <div className="stat-label">Birds in manifest</div>
              </div>
              <div className="stat-card">
                <div className="stat-number">{manifest.beats.length}</div>
                <div className="stat-label">Beat patterns</div>
              </div>
            </div>

            <div className="admin-section">
              <div className="admin-section-title">Dataset Stats</div>
              <div className="admin-section-coming">Coming soon — per-species counts, frequency &amp; onset distributions.</div>
            </div>

            <div className="admin-section">
              <div className="admin-section-title">Future: Trigger Reprocessing</div>
              <div className="admin-section-coming">Coming soon — re-run feature extraction and asset preparation from the browser.</div>
            </div>

            <button className="btn admin-logout" onClick={handleLogout}>Log out</button>
          </div>
        )}
      </div>
    </div>
  );
}
