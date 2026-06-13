import { useEffect, useState } from 'react';
import { playMidi, stopMidi } from '../utils/midiPlayer';

// Resolve a manifest-relative path against Vite's base URL.
function asset(path) {
  if (!path) return null;
  return `${import.meta.env.BASE_URL}${path}`.replace(/\/{2,}/g, '/');
}

export default function LibraryPage() {
  const [manifest, setManifest] = useState(null);
  const [error, setError] = useState(null);
  const [playingKey, setPlayingKey] = useState(null);
  const [progress, setProgress] = useState({ pct: 0, time: '0:00' });

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}library_manifest.json`)
      .then((r) => {
        if (!r.ok) throw new Error('manifest not found');
        return r.json();
      })
      .then(setManifest)
      .catch((e) => setError(e.message));

    // Stop any MIDI when leaving the page
    return () => stopMidi();
  }, []);

  function fmt(sec) {
    const m = Math.floor(sec / 60);
    return `${m}:${String(Math.floor(sec % 60)).padStart(2, '0')}`;
  }

  async function handleMidi(slug, midUrl) {
    try {
      await playMidi(
        slug,
        midUrl,
        {
          onProgress: (pct, elapsed) =>
            setProgress({ pct, time: fmt(elapsed) }),
          onEnd: () => { setPlayingKey(null); setProgress({ pct: 0, time: '0:00' }); },
        },
      );
      // playMidi toggles: if it stopped the same row, currentlyPlaying is null
      setPlayingKey((prev) => (prev === slug ? null : slug));
      setProgress({ pct: 0, time: '0:00' });
    } catch (e) {
      alert('Could not play MIDI: ' + e.message);
      setPlayingKey(null);
    }
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
                      onPlay={() => { stopMidi(); setPlayingKey(null); }}
                      src={asset(e.mp3)}
                    />
                  ) : (
                    <span className="dash-dim">— no MP3</span>
                  )}
                </td>
                <td className="dash-dim">{e.duration || '—'}</td>
                <td>
                  {e.mid ? (
                    <div className="dash-midi-cell">
                      <button
                        className={'btn-midi' + (playingKey === e.slug ? ' playing' : '')}
                        onClick={() => handleMidi(e.slug, asset(e.mid))}
                      >
                        {playingKey === e.slug ? '⏹ Stop' : '🎹 Play MIDI'}
                      </button>
                      <span className="dash-dim dash-notes">{e.notes} notes</span>
                      {playingKey === e.slug && (
                        <div className="dash-progress">
                          <div className="dash-bar-wrap">
                            <div className="dash-bar-fill" style={{ width: `${progress.pct}%` }} />
                          </div>
                          <span>{progress.time}</span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="dash-dim">— no MIDI</span>
                  )}
                </td>
                <td>
                  {e.arranged ? (
                    <audio
                      controls
                      preload="none"
                      className="dash-audio"
                      onPlay={() => { stopMidi(); setPlayingKey(null); }}
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
