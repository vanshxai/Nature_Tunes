import { useEffect, useMemo, useRef, useState } from 'react';
import Header from './components/Header';
import BeatControls from './components/BeatControls';
import Timeline from './components/Timeline';
import BirdLibrary from './components/BirdLibrary';
import AdminPanel from './components/AdminPanel';
import { useAudioEngine } from './hooks/useAudioEngine';
import { useTimeline } from './hooks/useTimeline';
import { buildShareUrl, copyToClipboard, parseShareUrl } from './utils/shareUtils';

// Parse any shared composition from the URL exactly once, before first render.
const SHARED = parseShareUrl();

export default function App() {
  const engine = useAudioEngine();
  const timeline = useTimeline(SHARED ? SHARED.tracks : null);

  const [selectedBeat, setSelectedBeat] = useState(SHARED ? SHARED.beat : 'none');
  const [bpm, setBpm] = useState(SHARED ? SHARED.bpm : 75);
  const [adminOpen, setAdminOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  // One-time "loaded from shared link" toast.
  const sharedToastShown = useRef(false);
  useEffect(() => {
    if (SHARED && !sharedToastShown.current) {
      sharedToastShown.current = true;
      showToast('Composition loaded from shared link');
    }
  }, []);

  // Keep Tone.Transport BPM in sync with the slider in real time.
  useEffect(() => {
    engine.setBpm(bpm);
  }, [bpm, engine]);

  const birdsById = useMemo(() => {
    const map = {};
    engine.manifest.birds.forEach((b) => { map[b.id] = b; });
    return map;
  }, [engine.manifest]);

  function showToast(message) {
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2000);
  }

  const handlePlayStop = () => {
    if (engine.isPlaying) {
      engine.stop();
    } else {
      engine.play(timeline.tracks, selectedBeat, bpm);
    }
  };

  const handleShare = async () => {
    const url = buildShareUrl(timeline.tracks, selectedBeat, bpm);
    const ok = await copyToClipboard(url);
    showToast(ok ? 'Copied!' : 'Copy failed — URL in address bar');
    // Reflect state in the address bar without reloading.
    window.history.replaceState(null, '', url);
  };

  if (engine.loading) {
    return (
      <>
        <Header isPlaying={false} onPlayStop={() => {}} onShare={() => {}} onOpenAdmin={() => {}} />
        <div className="loading-screen">
          <div className="loading-spinner" />
          <div>Loading bird sounds…</div>
        </div>
      </>
    );
  }

  return (
    <>
      <Header
        isPlaying={engine.isPlaying}
        onPlayStop={handlePlayStop}
        onShare={handleShare}
        onOpenAdmin={() => setAdminOpen(true)}
      />

      <main className="app-main">
        <BeatControls
          selectedBeat={selectedBeat}
          onSelectBeat={setSelectedBeat}
          bpm={bpm}
          onBpmChange={setBpm}
        />

        <Timeline
          tracks={timeline.tracks}
          birdsById={birdsById}
          canAddTrack={timeline.canAddTrack}
          canDeleteTrack={timeline.canDeleteTrack}
          onDropBird={timeline.placeBrick}
          onRemoveBrick={timeline.removeBrick}
          onAddTrack={timeline.addTrack}
          onDeleteTrack={timeline.deleteTrack}
          onVolumeChange={timeline.setVolume}
          onToggleMute={timeline.toggleMute}
        />

        <BirdLibrary
          birds={engine.manifest.birds}
          beats={engine.manifest.beats}
          onPreviewBird={engine.previewBird}
          onPreviewBeat={engine.previewBeat}
        />
      </main>

      {adminOpen && (
        <AdminPanel manifest={engine.manifest} onClose={() => setAdminOpen(false)} />
      )}

      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
