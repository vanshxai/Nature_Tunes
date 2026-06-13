// Shared MIDI playback engine for the Library page.
// Renders .mid files as piano via soundfont-player + midi-player-js (loaded
// from CDN in index.html, exposed as window.Soundfont / window.MidiPlayer).
//
// Only one MIDI plays at a time. Supports play / pause / resume / replay / stop.
// Callers pass callbacks for progress + end so the UI can reflect state without
// this module knowing about React.

let audioCtx = null;
let instrument = null;
let player = null;
let currentKey = null;          // which row is loaded
let currentState = 'idle';      // 'idle' | 'playing' | 'paused'
let activeNotes = [];
let callbacks = {};
let totalTicks = 0;

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

/**
 * Resume/start the AudioContext. MUST be called synchronously inside a user
 * gesture (e.g. the Play click) — browsers only honour resume() while the
 * gesture's activation is still valid, which expires after async awaits.
 */
export function unlockAudio() {
  ensureCtx();
  if (audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => { /* noop */ });
  }
}

/** Warm the soundfont cache so the first Play has no download delay. */
export function preloadInstrument() {
  if (!window.Soundfont) return Promise.resolve(null);
  return loadInstrument().catch(() => null);
}

function silenceNotes() {
  activeNotes.forEach((n) => { try { n.stop(); } catch (e) { /* noop */ } });
  activeNotes = [];
}

export function getState() {
  return { key: currentKey, state: currentState };
}

/**
 * Load a MIDI file by URL and start playing from the beginning.
 * @param {string} key  unique id for the calling row
 * @param {string} url  URL to the .mid file
 * @param {object} cbs  { onProgress(pct, elapsedSec), onEnd() }
 */
export async function play(key, url, cbs = {}) {
  stop();                       // tear down anything currently loaded

  const inst = await loadInstrument();
  if (audioCtx.state === 'suspended') await audioCtx.resume();

  const resp = await fetch(url);
  if (!resp.ok) throw new Error('Could not fetch MIDI');
  const arrayBuf = await resp.arrayBuffer();

  callbacks = cbs;
  totalTicks = 0;

  player = new window.MidiPlayer.Player((event) => {
    if (event.name === 'Note on' && event.velocity > 0) {
      const note = inst.play(event.noteName, audioCtx.currentTime, {
        gain: (event.velocity / 127) * 1.2,
      });
      activeNotes.push(note);
      if (activeNotes.length > 80) activeNotes = activeNotes.slice(-50);
    }
  });

  player.on('fileLoaded', () => { totalTicks = player.getTotalTicks(); });

  player.on('playing', (obj) => {
    if (callbacks.onProgress && totalTicks) {
      const pct = Math.min(100, (obj.tick / totalTicks) * 100);
      const elapsed = player.getSongTime() - player.getSongTimeRemaining();
      callbacks.onProgress(pct, Math.max(0, elapsed));
    }
  });

  player.on('endOfFile', () => {
    silenceNotes();
    currentState = 'idle';
    currentKey = null;
    if (callbacks.onEnd) callbacks.onEnd();
  });

  player.loadArrayBuffer(arrayBuf);
  player.play();
  currentKey = key;
  currentState = 'playing';
}

/** Pause the current playback, retaining position. Silences ringing notes. */
export function pause() {
  if (player && currentState === 'playing') {
    player.pause();
    silenceNotes();
    currentState = 'paused';
  }
}

/** Resume from the paused position. */
export function resume() {
  if (player && currentState === 'paused') {
    if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
    player.play();
    currentState = 'playing';
  }
}

/** Restart the current file from the beginning. */
export function replay() {
  if (player) {
    silenceNotes();
    player.stop();              // resets position to start
    if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
    player.play();
    currentState = 'playing';
  }
}

/** Seek to a percentage (0–100) within the current file. */
export function seekTo(pct) {
  if (player) {
    silenceNotes();
    player.skipToPercent(Math.max(0, Math.min(100, pct)));
    if (currentState === 'paused') {
      // stay paused but update position
    } else {
      player.play();
      currentState = 'playing';
    }
  }
}

/** Stop and fully tear down the current playback. */
export function stop() {
  if (player) {
    try { player.stop(); } catch (e) { /* noop */ }
    player = null;
  }
  silenceNotes();
  currentKey = null;
  currentState = 'idle';
}
