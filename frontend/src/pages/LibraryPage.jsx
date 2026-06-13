import { useEffect, useState } from 'react';
import { play, pause, resume, replay, stop, unlockAudio, preloadInstrument } from '../utils/midiPlayer';

// Resolve a manifest-relative path against Vite's base URL.
function asset(path) {
  if (!path) return null;
  return `${import.meta.env.BASE_URL}${path}`.replace(/\/{2,}/g, '/');
}

export default function LibraryPage() {
  const [manifest, setManifest] = useState(null);
  const [error, setError] = useState(null);
  const [activeKey, setActiveKey] = useState(null);     // slug currently loaded
  const [playState, setPlayState] = useState('idle');    // 'idle' | 'playing' | 'paused'
  const [progress, setProgress] = useState({ pct: 0, time: '0:00' });

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}library_manifest.json`)
      .then((r) => {
        if (!r.ok) throw new Error('manifest not found');
        return r.json();
      })
      .then(setManifest)
      .catch((e) => setError(e.message));

    // Warm the piano samples so the first Play is instant.
    preloadInstrument();

    // Stop any MIDI when leaving the page
    return () => stop();
  }, []);

  function fmt(sec) {
    const m = Math.floor(sec / 60);
    return `${m}:${String(Math.floor(sec % 60)).padStart(2, '0')}`;
  }

  function resetUi() {
    setActiveKey(null);
    setPlayState('idle');
    setProgress({ pct: 0, time: '0:00' });
  }

  async function handlePlay(slug, midUrl) {
    // Unlock audio synchronously within the click gesture, before any await,
    // or the browser keeps the AudioContext muted.
    unlockAudio();
    setActiveKey(slug);
    setPlayState('loading');
    setProgress({ pct: 0, time: '0:00' });
    try {
      await play(slug, midUrl, {
        onProgress: (pct, elapsed) => setProgress({ pct, time: fmt(elapsed) }),
        onEnd: () => resetUi(),
      });
      setPlayState('playing');
    } catch (e) {
      alert('Could not play MIDI: ' + e.message);
      resetUi();
    }
  }

  function handlePause() {
    pause();
    setPlayState('paused');
  }

  function handleResume() {
    resume();
    setPlayState('playing');
  }

  function handleReplay() {
    replay();
    setPlayState('playing');
    setProgress({ pct: 0, time: '0:00' });
  }

  function handleStop() {
    stop();
    resetUi();
  }

  // Stop MIDI when an <audio> element starts playing.
  function onAudioPlay() {
    stop();
    resetUi();
  }

  if (error) {
    return (
      <main className="dash-main">
        <div className="dash-empty">
          <div className="dash-empty-icon">⚠️</div>
          <div className="dash-empty-text">Could not load the library</div>
          <div className="dash-empty-sub">{error}</div>
        </div>
      </main>
    );
  }

  if (!manifest) {
    return (
      <main className="dash-main">
        <div className="loading-screen">
          <div className="loading-spinner" />
          <div>Loading library…</div>
        </div>
      </main>
    );
  }

  function renderMidiCell(e) {
    if (!e.mid) return <span className="dash-dim">— no MIDI</span>;

    const isActive = activeKey === e.slug;
    const midUrl = asset(e.mid);

    return (
      <div className="dash-midi-cell">
        {!isActive ? (
          <button className="btn-midi" onClick={() => handlePlay(e.slug, midUrl)}>
            🎹 Play
          </button>
        ) : playState === 'loading' ? (
          <button className="btn-midi loading" disabled>⏳ Loading…</button>
        ) : (
          <div className="midi-transport">
            {playState === 'playing' ? (
              <button className="tbtn" title="Pause" onClick={handlePause}>⏸</button>
            ) : (
              <button className="tbtn" title="Resume" onClick={handleResume}>▶</button>
            )}
            <button className="tbtn" title="Replay from start" onClick={handleReplay}>⟳</button>
            <button className="tbtn tbtn-stop" title="Stop" onClick={handleStop}>⏹</button>
          </div>
        )}

        <span className="dash-dim dash-notes">{e.notes} notes</span>

        {isActive && (
          <div className="dash-progress">
            <div className="dash-bar-wrap">
              <div className="dash-bar-fill" style={{ width: `${progress.pct}%` }} />
            </div>
            <span>{progress.time}</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <main className="dash-main">
      <div className="dash-statusbar">
        <div className="dash-stat">
          <div className="dash-stat-num">{manifest.count}</div>
          <div className="dash-stat-label">Species</div>
        </div>
        <div className="dash-stat-sep" />
        <div className="dash-stat">
          <div className="dash-stat-num">{manifest.midi_count}</div>
          <div className="dash-stat-label">MIDI files</div>
        </div>
        <div className="dash-stat-sep" />
        <div className="dash-stat">
          <div className="dash-stat-num">{manifest.mp3_count}</div>
          <div className="dash-stat-label">MP3 files</div>
        </div>
        <div className="dash-stat-sep" />
        <div className="dash-stat">
          <div className="dash-stat-num">{manifest.arranged_count}</div>
          <div className="dash-stat-label">Arranged</div>
        </div>
      </div>

      <div className="dash-table-wrap">
        <table className="dash-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Species</th>
              <th>Original MP3</th>
              <th>Duration</th>
              <th>MIDI (piano)</th>
              <th>Arranged mix</th>
              <th>Download</th>
            </tr>
          </thead>
          <tbody>
            {manifest.species.map((e, i) => (
              <tr key={e.slug}>
                <td className="dash-idx">{i + 1}</td>
                <td>
                  <div className="dash-species">{e.species}</div>
                  <div className="dash-slug">{e.slug}/</div>
                </td>
                <td>
                  {e.mp3 ? (
                    <audio
                      controls
                      preload="none"
                      className="dash-audio"
                      onPlay={onAudioPlay}
                      src={asset(e.mp3)}
                    />
                  ) : (
                    <span className="dash-dim">— no MP3</span>
                  )}
                </td>
                <td className="dash-dim">{e.duration || '—'}</td>
                <td>{renderMidiCell(e)}</td>
                <td>
                  {e.arranged ? (
                    <audio
                      controls
                      preload="none"
                      className="dash-audio"
                      onPlay={onAudioPlay}
                      src={asset(e.arranged)}
                    />
                  ) : (
                    <span className="dash-dim">—</span>
                  )}
                </td>
                <td>
                  {e.mid ? (
                    <a className="btn-dl" href={asset(e.mid)} download>
                      ⬇ .mid
                    </a>
                  ) : (
                    <span className="btn-dl disabled">⬇ .mid</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <footer className="dash-footer">
        NatureTunes library &nbsp;·&nbsp; Original MP3 = field recording &nbsp;·&nbsp;
        MIDI = neural pitch transcription rendered as piano &nbsp;·&nbsp;
        Arranged = MIDI + flute/strings layered over the recording
      </footer>
    </main>
  );
}
