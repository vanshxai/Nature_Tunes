import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import '../styles/landing.css';

const TRACKS = [
  {
    slug: 'hermit_thrush',
    name: 'Forest Dawn',
    species: 'Hermit Thrush',
    condition: 'For Anxiety',
    color: '#1a4a2a',
    accent: '#4aaa6a',
    badgeBg: 'rgba(74,170,106,0.15)',
    badgeColor: '#4aaa6a',
    audio: 'audio/final/hermit_thrush_naturetunes.mp3',
  },
  {
    slug: 'common_nightingale',
    name: 'Moonlit Forest',
    species: 'Common Nightingale',
    condition: 'For Sleep',
    color: '#0d1a3a',
    accent: '#4a7acc',
    badgeBg: 'rgba(74,122,204,0.15)',
    badgeColor: '#4a7acc',
    audio: 'audio/final/common_nightingale_naturetunes.mp3',
  },
  {
    slug: 'wood_thrush',
    name: 'Sacred Morning',
    species: 'Wood Thrush',
    condition: 'For Focus',
    color: '#2a1a00',
    accent: '#c9a84c',
    badgeBg: 'rgba(201,168,76,0.15)',
    badgeColor: '#c9a84c',
    audio: null,
  },
  {
    slug: 'canyon_wren',
    name: 'Desert Echo',
    species: 'Canyon Wren',
    condition: 'For Sleep',
    color: '#2a1008',
    accent: '#cc7a4a',
    badgeBg: 'rgba(204,122,74,0.15)',
    badgeColor: '#cc7a4a',
    audio: null,
  },
  {
    slug: 'veery',
    name: 'Twilight Spiral',
    species: 'Veery',
    condition: 'For Overthinking',
    color: '#1a0a2a',
    accent: '#9a6acc',
    badgeBg: 'rgba(154,106,204,0.15)',
    badgeColor: '#9a6acc',
    audio: null,
  },
];

// Firefly particle animation
function useFireflies(canvasRef) {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let raf;

    const resize = () => {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const particles = Array.from({ length: 55 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 1.8 + 0.4,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
      alpha: Math.random(),
      dalpha: (Math.random() * 0.008 + 0.002) * (Math.random() > 0.5 ? 1 : -1),
      gold: Math.random() > 0.65,
    }));

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        p.alpha += p.dalpha;
        if (p.alpha <= 0 || p.alpha >= 1) p.dalpha *= -1;
        p.alpha = Math.max(0, Math.min(1, p.alpha));
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = p.gold
          ? `rgba(201,168,76,${p.alpha * 0.7})`
          : `rgba(74,170,106,${p.alpha * 0.5})`;
        ctx.fill();
      });
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }, [canvasRef]);
}

// Waveform bars
function Waveform() {
  const bars = 28;
  const heights = Array.from({ length: bars }, (_, i) => {
    const mid = bars / 2;
    const dist = Math.abs(i - mid) / mid;
    return 0.25 + (1 - dist * dist) * 0.75;
  });
  return (
    <div className="nt-waveform">
      {heights.map((h, i) => (
        <div
          key={i}
          className="nt-waveform-bar"
          style={{
            height: `${h * 100}%`,
            animationDelay: `${(i / bars) * 1.4}s`,
          }}
        />
      ))}
    </div>
  );
}

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

function TrackCard({ track, onPlayAttempt }) {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef(null);

  function togglePreview() {
    if (!audioRef.current) return;
    if (playing) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setPlaying(false);
    } else {
      if (onPlayAttempt) {
        onPlayAttempt(() => { audioRef.current.play(); setPlaying(true); });
      } else {
        audioRef.current.play();
        setPlaying(true);
      }
    }
  }

  return (
    <div className="nt-track-card">
      <svg className="nt-track-orb" viewBox="0 0 64 64">
        <defs>
          <radialGradient id={`g-${track.slug}`} cx="40%" cy="35%" r="65%">
            <stop offset="0%" stopColor={track.accent} stopOpacity="0.9" />
            <stop offset="100%" stopColor={track.color} stopOpacity="1" />
          </radialGradient>
        </defs>
        <circle cx="32" cy="32" r="32" fill={`url(#g-${track.slug})`} />
        <circle cx="32" cy="32" r="32" fill="none" stroke={track.accent} strokeWidth="1" strokeOpacity="0.3" />
      </svg>

      <div>
        <div className="nt-track-name">{track.name}</div>
        <div className="nt-track-species">{track.species}</div>
      </div>

      <span
        className="nt-track-badge"
        style={{ background: track.badgeBg, color: track.badgeColor }}
      >
        {track.condition}
      </span>

      <div className="nt-track-btns">
        {track.audio ? (
          <button className="nt-track-preview" onClick={togglePreview}>
            {playing ? '⏸' : '▶'} {playing ? 'Pause' : '30s Preview'}
          </button>
        ) : (
          <span className="nt-track-preview" style={{ opacity: 0.4, cursor: 'default' }}>
            🔒 Coming Soon
          </span>
        )}
        <Link to="/listen" className="nt-track-link">Full Track →</Link>
      </div>

      {track.audio && (
        <audio
          ref={audioRef}
          src={`${import.meta.env.BASE_URL}${track.audio}`}
          onEnded={() => setPlaying(false)}
          preload="none"
        />
      )}
    </div>
  );
}

export default function LandingPage() {
  const canvasRef = useRef(null);
  useFireflies(canvasRef);

  const [showModal, setShowModal] = useState(false);
  const [pendingPlay, setPendingPlay] = useState(null);

  const alreadySignedUp = () => localStorage.getItem(SIGNED_UP_KEY) === 'true';

  function handlePlayAttempt(playFn) {
    if (alreadySignedUp()) {
      playFn();
    } else {
      setPendingPlay(() => playFn);
      setShowModal(true);
    }
  }

  function handleSignUp() {
    localStorage.setItem(SIGNED_UP_KEY, 'true');
    setShowModal(false);
    if (pendingPlay) { pendingPlay(); setPendingPlay(null); }
  }

  function handleDismiss() {
    setShowModal(false);
    if (pendingPlay) { pendingPlay(); setPendingPlay(null); }
  }

  return (
    <div className="nt-page">
      {showModal && <SignupModal onSignUp={handleSignUp} onDismiss={handleDismiss} />}

      {/* Nav */}
      <nav className="nt-nav">
        <div className="nt-nav-brand">NatureTunes</div>
        <div className="nt-nav-links">
          <a className="nt-nav-link" href="#science">Science</a>
          <Link className="nt-nav-link" to="/listen">Listen</Link>
          <Link className="nt-nav-link" to="/admin" style={{ opacity: 0.5, fontSize: 12 }}>Admin</Link>
          <a className="nt-nav-cta" href={FORM_URL} target="_blank" rel="noopener noreferrer">Sign Up →</a>
        </div>
      </nav>

      {/* Hero */}
      <section className="nt-hero">
        <div className="nt-hero-bg" />
        <canvas ref={canvasRef} className="nt-firefly-canvas" />
        <div className="nt-hero-content">
          <h1 className="nt-logo-text">
            Nature<span className="nt-logo-accent">Tunes</span>
          </h1>
          <p className="nt-tagline">Your mind deserves nature.</p>
          <p className="nt-sub-tagline">
            Therapeutic music from real bird field recordings.<br />
            Engineered for anxiety, sleep and calm.
          </p>
          <Waveform />
          <div className="nt-hero-btns">
            <Link className="nt-btn-primary" to="/listen">Listen Free →</Link>
            <a className="nt-btn-secondary" href="https://forms.gle/uRMnBpcXmuwBvcRa9" target="_blank" rel="noopener noreferrer">Sign Up for Early Access</a>
            <a className="nt-btn-secondary" href="#science">Learn the Science ↓</a>
          </div>
        </div>
      </section>

      {/* Section 2 — Problem */}
      <section className="nt-problem">
        <h2 className="nt-problem-headline">
          Anxiety.<br />Overthinking.<br />Sleepless nights.
        </h2>
        <p className="nt-problem-sub">
          280 million people worldwide live with anxiety disorders. Most solutions feel artificial.
          We went back to nature.
        </p>
      </section>

      {/* Section 3 — How It Works */}
      <section className="nt-section-full">
        <div className="nt-section-inner" style={{ padding: '0 24px' }}>
          <div className="nt-section-label">How It Works</div>
          <h2 className="nt-section-title">Built different. From the ground up.</h2>
          <div className="nt-how-grid">
            {[
              {
                icon: '🎙️',
                title: 'Real Field Recordings',
                body: '814 real bird recordings from 39 countries. Every sound you hear was sung by a real bird in the wild.',
              },
              {
                icon: '🧠',
                title: 'Frequency Engineered',
                body: 'Binaural beats embedded at clinically researched frequencies. Alpha waves for anxiety. Delta waves for sleep. Beta waves for focus.',
              },
              {
                icon: '🌿',
                title: 'Science Backed',
                body: 'Peer-reviewed research confirms birdsong reduces cortisol and anxiety measurably. We built a product around that science.',
              },
            ].map(c => (
              <div key={c.title} className="nt-how-card">
                <div className="nt-how-icon">{c.icon}</div>
                <div className="nt-how-title">{c.title}</div>
                <div className="nt-how-body">{c.body}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Section 4 — Tracks */}
      <section className="nt-section">
        <div className="nt-section-label">The Tracks</div>
        <h2 className="nt-section-title">Five moods. Five recordings. One library.</h2>
        <div className="nt-tracks-grid">
          {TRACKS.map(t => <TrackCard key={t.slug} track={t} onPlayAttempt={handlePlayAttempt} />)}
        </div>
      </section>

      {/* Section 5 — Testimonials */}
      <section className="nt-section-full">
        <div className="nt-section-inner" style={{ padding: '0 24px' }}>
          <div className="nt-section-label">Early Listeners</div>
          <h2 className="nt-section-title">What people are saying.</h2>
          <div className="nt-testimonials">
            <div className="nt-testimonial">
              <p className="nt-testimonial-quote">
                The second track is so good — I was feeling sleepy. I'll use this for sleeping now.
              </p>
              <div className="nt-testimonial-author">— Early listener, Mumbai</div>
            </div>
            <div className="nt-testimonial">
              <p className="nt-testimonial-quote">
                The music is soothing and calming. It genuinely helps.
              </p>
              <div className="nt-testimonial-author">— Early listener</div>
            </div>
          </div>
        </div>
      </section>

      {/* Section 6 — Science */}
      <section id="science" className="nt-section">
        <div className="nt-section-label">The Evidence</div>
        <h2 className="nt-section-title">Not just music. Evidence.</h2>
        <div className="nt-science-pills">
          {[
            'Stobbe et al. 2022 — Birdsong reduces anxiety and paranoia. Scientific Reports.',
            'Ratcliffe 2021 — Nature sounds restore mental wellbeing. Frontiers in Psychology.',
            'Meta-analysis 2025 — Music therapy significantly reduces anxiety across clinical settings.',
          ].map(c => (
            <div key={c} className="nt-science-pill">
              <div className="nt-science-pill-dot" />
              <span>{c}</span>
            </div>
          ))}
        </div>
        <p className="nt-science-disclaimer">
          NatureTunes is not a medical device. It is a wellness tool informed by peer-reviewed research.
        </p>
      </section>

      {/* Section 7 — CTA */}
      <section className="nt-cta-section">
        <h2 className="nt-cta-title">Start listening. Free.</h2>
        <p className="nt-cta-sub">No account needed. Just press play.</p>
        <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link className="nt-btn-primary" to="/listen">Open the Library →</Link>
          <a className="nt-btn-secondary" href="https://forms.gle/uRMnBpcXmuwBvcRa9" target="_blank" rel="noopener noreferrer">Sign Up for Early Access</a>
        </div>
        <p className="nt-cta-coming">
          Premium plans coming soon — personalized tracks for your mental state
        </p>
      </section>

      {/* Footer */}
      <footer className="nt-footer">
        <div>
          <div className="nt-footer-brand">NatureTunes</div>
          <div className="nt-footer-tagline">Built from real nature. Backed by science.</div>
        </div>
        <div className="nt-footer-links">
          <Link to="/listen" className="nt-footer-link">Listen</Link>
          <a href="#science" className="nt-footer-link">Science</a>
          <Link to="/admin" className="nt-footer-link">Admin</Link>
        </div>
        <div className="nt-footer-copy">NatureTunes © 2026 · naturetunes.space</div>
      </footer>
    </div>
  );
}
