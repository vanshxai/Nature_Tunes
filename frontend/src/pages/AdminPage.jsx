import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import LibraryPage from './LibraryPage.jsx';
import App from '../App.jsx';
import '../styles/landing.css';

const CORRECT = import.meta.env.VITE_ADMIN_PASSWORD || 'ntadmin';

export default function AdminPage() {
  const navigate = useNavigate();
  const [input, setInput]       = useState('');
  const [error, setError]       = useState('');
  const [authed, setAuthed]     = useState(false);
  const [view, setView]         = useState('library'); // 'library' | 'composer'

  function handleSubmit(e) {
    e.preventDefault();
    if (input.trim() === CORRECT) {
      setAuthed(true);
      setError('');
    } else {
      setError('Incorrect password. Try again.');
      setInput('');
    }
  }

  if (!authed) {
    return (
      <div className="admin-gate">
        <div className="admin-gate-card">
          <div className="admin-gate-logo">NatureTunes</div>
          <div className="admin-gate-sub">Admin access only</div>
          <form onSubmit={handleSubmit}>
            <input
              className="admin-gate-input"
              type="password"
              placeholder="Enter password"
              value={input}
              onChange={e => { setInput(e.target.value); setError(''); }}
              autoFocus
            />
            <button className="admin-gate-btn" type="submit">Enter →</button>
            <div className="admin-gate-error">{error}</div>
          </form>
          <div style={{ marginTop: 20 }}>
            <a href="/" style={{ fontSize: 13, color: 'var(--nt-muted)', textDecoration: 'none' }}>← Back to home</a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      {/* Admin sub-nav */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 24,
        padding: '12px 28px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        fontFamily: 'Inter, sans-serif',
      }}>
        <span style={{ color: 'var(--accent)', fontWeight: 700, fontSize: 14 }}>
          🌿 Admin
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          {['library', 'composer'].map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              style={{
                padding: '6px 16px',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                background: view === v ? 'var(--accent)' : 'transparent',
                color: view === v ? '#0a0a0a' : 'var(--text-secondary)',
                border: '1px solid ' + (view === v ? 'var(--accent)' : 'var(--border)'),
                cursor: 'pointer',
                textTransform: 'capitalize',
                fontFamily: 'Inter, sans-serif',
              }}
            >
              {v}
            </button>
          ))}
        </div>
        <button
          onClick={() => { setAuthed(false); navigate('/'); }}
          style={{
            marginLeft: 'auto', fontSize: 12, color: 'var(--text-secondary)',
            background: 'none', border: 'none', cursor: 'pointer',
            fontFamily: 'Inter, sans-serif',
          }}
        >
          Sign out
        </button>
      </div>

      {view === 'library'  && <LibraryPage />}
      {view === 'composer' && <App />}
    </div>
  );
}
