import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import '../styles/landing.css';

const FORM_URL = 'https://forms.gle/uRMnBpcXmuwBvcRa9';
const SIGNED_UP_KEY = 'nt_signed_up';

function SignupModal({ onSignUp, onDismiss }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 999,
      background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24,
    }}>
      <div style={{
        background: '#111a14', border: '1px solid var(--nt-border)',
        borderRadius: 16, padding: '40px 36px', maxWidth: 420, width: '100%',
        textAlign: 'center', boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
      }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>🎧</div>
        <h3 style={{ fontFamily: 'Playfair Display, serif', fontSize: 22, color: 'var(--nt-white)', marginBottom: 10 }}>
          Enjoy this track free
        </h3>
        <p style={{ fontSize: 14, color: 'var(--nt-muted)', lineHeight: 1.7, marginBottom: 28 }}>
          Sign up for early access to get notified when new tracks drop and unlock premium features.
        </p>
        <a
          href={FORM_URL}
          target="_blank"
          rel="noopener noreferrer"
          onClick={onSignUp}
          style={{
            display: 'block', width: '100%', padding: '13px 0',
            background: 'var(--nt-gold)', color: '#0a0a0a',
            fontWeight: 700, fontSize: 14, borderRadius: 8,
            textDecoration: 'none', marginBottom: 12,
          }}
        >
          Sign Up for Early Access →
        </a>
        <button
          onClick={onDismiss}
          style={{
            background: 'none', border: 'none', color: 'var(--nt-muted)',
            fontSize: 13, cursor: 'pointer', textDecoration: 'underline',
          }}
        >
          Maybe later — just let me listen
        </button>
      </div>
    </div>
  );
}

// All five tracks. `audio` points to the pedalboard-mastered final mix.
// Tracks with no final file yet are hidden automatically — set audio: null.
const TRACKS = [
  {
    slug: 'hermit_thrush',
    name: 'Forest Dawn',
    species: 'Hermit Thrush',
    condition: 'For Anxiety',
    duration: '5:40',
    color: '#1a4a2a',
    accent: '#4aaa6a',
    badgeBg: 'rgba(74,170,106,0.15)',
    badgeColor: '#4aaa6a',
    audio: 'audio/final/hermit_thrush_naturetunes.mp3',
    desc: 'Gentle flute and strings layered over a real hermit thrush recorded at dawn. Binaural beats at 432 Hz / 440 Hz embedded throughout. Grounding and calming.',
  },
  {
    slug: 'common_nightingale',
    name: 'Moonlit Forest',
    species: 'Common Nightingale',
    condition: 'For Sleep',
    duration: '2:47',
    color: '#0d1a3a',
    accent: '#4a7acc',
    badgeBg: 'rgba(74,122,204,0.15)',
    badgeColor: '#4a7acc',
    audio: 'audio/final/common_nightingale_naturetunes.mp3',
    desc: "The world's most celebrated songbird. Rich, complex melodies with string pads and binaural beats for deep sleep.",
  },
  {
    slug: 'wood_thrush',
    name: 'Sacred Morning',
    species: 'Wood Thrush',
    condition: 'For Focus',
    duration: null,
    color: '#2a1a00',
    accent: '#c9a84c',
    badgeBg: 'rgba(201,168,76,0.15)',
    badgeColor: '#c9a84c',
    audio: null,   // no final mix yet
    desc: 'Bright, clear calls layered with warm tones. Ideal background for deep work and concentration.',
  },
  {
    slug: 'canyon_wren',
    name: 'Desert Echo',
    species: 'Canyon Wren',
    condition: 'For Sleep',
    duration: null,
    color: '#2a1008',
    accent: '#cc7a4a',
    badgeBg: 'rgba(204,122,74,0.15)',
    badgeColor: '#cc7a4a',
    audio: null,   // no final mix yet
    desc: 'Cascading desert calls with warm reverb. Puts the mind in a vast, open, quiet place.',
  },
  {
    slug: 'veery',
    name: 'Twilight Spiral',
    species: 'Veery',
    condition: 'For Overthinking',
    duration: null,
    color: '#1a0a2a',
    accent: '#9a6acc',
    badgeBg: 'rgba(154,106,204,0.15)',
    badgeColor: '#9a6acc',
    audio: null,   // no final mix yet
    desc: "The veery's spiraling, flute-like call is uniquely effective at quieting a racing mind.",
  },
];

const AVAILABLE = TRACKS.filter(t => t.audio !== null);
const COMING    = TRACKS.filter(t => t.audio === null);

function TrackPlayer({ track }) {
  const [unlocked, setUnlocked] = useState(
    () => localStorage.getItem(SIGNED_UP_KEY) === 'true'
  );
  const [showModal, setShowModal] = useState(false);
  const audioRef = useRef(null);

  function handlePlay() {
    if (unlocked) return; // native audio takes over after unlock
    setShowModal(true);
  }

  function unlock() {
    localStorage.setItem(SIGNED_UP_KEY, 'true');
    setUnlocked(true);
    setShowModal(false);
    setTimeout(() => audioRef.current?.play(), 50);
  }

  function dismiss() {
    setUnlocked(true);
    setShowModal(false);
    setTimeout(() => audioRef.current?.play(), 50);
  }

  return (
    <>
      {showModal && <SignupModal onSignUp={unlock} onDismiss={dismiss} />}
      {unlocked ? (
        <audio
          ref={audioRef}
          controls
          preload="none"
          className="listen-audio"
          src={`${import.meta.env.BASE_URL}${track.audio}`}
        />
      ) : (
        <button
          onClick={handlePlay}
          className="listen-audio"
          style={{
            display: 'flex', alignItems: 'center', gap: 10,
            background: 'rgba(201,168,76,0.1)', border: '1px solid rgba(201,168,76,0.3)',
            borderRadius: 8, padding: '10px 20px', cursor: 'pointer',
            color: 'var(--nt-gold)', fontFamily: 'Inter, sans-serif',
            fontSize: 14, fontWeight: 600, width: '100%',
          }}
        >
          ▶ Play Full Track
        </button>
      )}
    </>
  );
}

export default function ListenPage() {
  return (
    <div className="listen-page">
      <nav className="nt-nav">
        <Link to="/" className="nt-nav-brand" style={{ textDecoration: 'none' }}>NatureTunes</Link>
        <div className="nt-nav-links">
          <Link className="nt-nav-link" to="/">Home</Link>
          <Link className="nt-nav-link" to="/admin" style={{ fontSize: 12, opacity: 0.5 }}>Admin</Link>
          <a className="nt-nav-cta" href="https://forms.gle/uRMnBpcXmuwBvcRa9" target="_blank" rel="noopener noreferrer">Sign Up →</a>
        </div>
      </nav>

      <div className="listen-header">
        <h1>The Library</h1>
        <p>
          Therapeutic tracks from real field recordings, mastered with spatial audio and binaural beats.
          Press play — no account needed.
        </p>
      </div>

      <div className="listen-grid">
        {AVAILABLE.map(track => (
          <div key={track.slug} className="listen-card">
            <div className="listen-card-top">
              <svg className="listen-orb" viewBox="0 0 52 52">
                <defs>
                  <radialGradient id={`lg-${track.slug}`} cx="40%" cy="35%" r="65%">
                    <stop offset="0%" stopColor={track.accent} stopOpacity="0.9" />
                    <stop offset="100%" stopColor={track.color} stopOpacity="1" />
                  </radialGradient>
                </defs>
                <circle cx="26" cy="26" r="26" fill={`url(#lg-${track.slug})`} />
              </svg>
              <div className="listen-info">
                <div className="listen-title">{track.species} — {track.name}</div>
                <div className="listen-meta">
                  {track.duration && <>{track.duration} · </>}
                  <span style={{
                    color: track.badgeColor,
                    background: track.badgeBg,
                    padding: '2px 8px',
                    borderRadius: 12,
                    fontSize: 11,
                    fontWeight: 600,
                  }}>
                    {track.condition}
                  </span>
                </div>
                <div style={{ fontSize: 13, color: 'var(--nt-muted)', lineHeight: 1.6, marginTop: 6 }}>
                  {track.desc}
                </div>
              </div>
            </div>
            <TrackPlayer track={track} />
          </div>
        ))}

        {/* Coming soon cards — shown but clearly marked */}
        {COMING.length > 0 && (
          <div style={{
            gridColumn: '1 / -1',
            borderTop: '1px solid var(--nt-border)',
            paddingTop: 28,
            marginTop: 8,
          }}>
            <div style={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: 2,
              textTransform: 'uppercase',
              color: 'var(--nt-gold)',
              marginBottom: 20,
            }}>
              Coming Soon
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
              {COMING.map(track => (
                <div key={track.slug} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '14px 20px',
                  background: 'var(--nt-card)',
                  border: '1px solid var(--nt-border)',
                  borderRadius: 12,
                  opacity: 0.55,
                  minWidth: 220,
                }}>
                  <svg width="36" height="36" viewBox="0 0 36 36">
                    <defs>
                      <radialGradient id={`cs-${track.slug}`} cx="40%" cy="35%" r="65%">
                        <stop offset="0%" stopColor={track.accent} stopOpacity="0.7" />
                        <stop offset="100%" stopColor={track.color} stopOpacity="1" />
                      </radialGradient>
                    </defs>
                    <circle cx="18" cy="18" r="18" fill={`url(#cs-${track.slug})`} />
                  </svg>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--nt-white)', fontFamily: 'Playfair Display, serif' }}>
                      {track.name}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--nt-muted)' }}>{track.species}</div>
                  </div>
                  <span style={{
                    marginLeft: 'auto',
                    fontSize: 10,
                    fontWeight: 600,
                    padding: '3px 8px',
                    borderRadius: 10,
                    background: track.badgeBg,
                    color: track.badgeColor,
                  }}>{track.condition}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <Link to="/" className="listen-back">← Back to home</Link>
    </div>
  );
}
