// Shared MIDI playback engine for the Library page.
// Renders .mid files as piano via soundfont-player + midi-player-js (loaded
// from CDN in index.html, exposed as window.Soundfont / window.MidiPlayer).
//
// Only one MIDI plays at a time. Callers pass callbacks for progress + end so
// the UI can reflect state without this module knowing about React.

let audioCtx = null;
let instrument = null;
let currentPlayer = null;
let currentKey = null;        // identifies which row is playing
let activeNotes = [];
let onEndCb = null;

function ensureCtx() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  return audioCtx;
}

async function loadInstrument() {
  if (instrument) return instrument;
  ensureCtx();
  if (!window.Soundfont) throw new Error('Soundfont library not loaded');
  instrument = await window.Soundfont.instrument(audioCtx, 'acoustic_grand_piano', {
    soundfont: 'MusyngKite',
  });
  return instrument;
}

export function currentlyPlaying() {
  return currentKey;
}

export function stopMidi() {
  if (currentPlayer) {
    try { currentPlayer.stop(); } catch (e) { /* noop */ }
    currentPlayer = null;
  }
  activeNotes.forEach((n) => { try { n.stop(); } catch (e) { /* noop */ } });
  activeNotes = [];
  const endedKey = currentKey;
  currentKey = null;
  if (onEndCb) {
    const cb = onEndCb;
    onEndCb = null;
    cb(endedKey);
  }
}

/**
 * Play a MIDI file by URL.
 * @param {string} key     unique id for the calling row
 * @param {string} url     URL to the .mid file
 * @param {object} cbs     { onProgress(pct, elapsedSec), onEnd(key) }
 */
export async function playMidi(key, url, cbs = {}) {
  // Toggle off if same row is already playing
  if (key === currentKey) {
    stopMidi();
    return;
  }
  stopMidi();

  const inst = await loadInstrument();
  if (audioCtx.state === 'suspended') await audioCtx.resume();

  const resp = await fetch(url);
  if (!resp.ok) throw new Error('Could not fetch MIDI');
  const arrayBuf = await resp.arrayBuffer();

  let totalTicks = 0;
  const player = new window.MidiPlayer.Player((event) => {
    if (event.name === 'Note on' && event.velocity > 0) {
      const note = inst.play(event.noteName, audioCtx.currentTime, {
        gain: (event.velocity / 127) * 1.2,
      });
      activeNotes.push(note);
      if (activeNotes.length > 60) activeNotes = activeNotes.slice(-40);
    }
  });

  player.on('fileLoaded', () => { totalTicks = player.getTotalTicks(); });

  player.on('playing', (obj) => {
    if (!cbs.onProgress || !totalTicks) return;
    const pct = (obj.tick / totalTicks) * 100;
    const elapsed = player.getSongTime() - player.getSongTimeRemaining();
    cbs.onProgress(Math.min(100, pct), Math.max(0, elapsed));
  });

  player.on('endOfFile', () => { stopMidi(); });

  player.loadArrayBuffer(arrayBuf);
  player.play();

  currentPlayer = player;
  currentKey = key;
  onEndCb = cbs.onEnd || null;
}
