import { useCallback, useEffect, useRef, useState } from 'react';
import * as Tone from 'tone';
import { SLOT_SECONDS, linearToDb } from '../utils/audioUtils';

/**
 * Owns all Tone.js resources: one Player per bird (loop=false), one Player per
 * beat (loop=true), preloaded via Tone.loaded(). Exposes imperative transport
 * controls plus a preview function.
 */
export function useAudioEngine() {
  const [loading, setLoading] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  const [manifest, setManifest] = useState({ birds: [], beats: [] });

  const birdPlayers = useRef(new Map()); // id -> Tone.Player
  const beatPlayers = useRef(new Map()); // id -> Tone.Player
  const startedRef = useRef(false);

  // ── Load manifest + preload all players ─────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function load() {
      const res = await fetch('/audio/manifest.json');
      const data = await res.json();
      if (cancelled) return;

      data.birds.forEach((bird) => {
        const player = new Tone.Player({ url: bird.file, loop: false }).toDestination();
        birdPlayers.current.set(bird.id, player);
      });

      data.beats.forEach((beat) => {
        const player = new Tone.Player({ url: beat.file, loop: true }).toDestination();
        beatPlayers.current.set(beat.id, player);
      });

      await Tone.loaded();
      if (cancelled) return;
      setManifest(data);
      setLoading(false);
    }

    load().catch((err) => {
      console.error('Audio engine load failed:', err);
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
      Tone.Transport.stop();
      Tone.Transport.cancel();
      birdPlayers.current.forEach((p) => p.dispose());
      beatPlayers.current.forEach((p) => p.dispose());
      birdPlayers.current.clear();
      beatPlayers.current.clear();
    };
  }, []);

  const ensureStarted = useCallback(async () => {
    if (!startedRef.current) {
      await Tone.start();
      startedRef.current = true;
    }
  }, []);

  const setBpm = useCallback((bpm) => {
    Tone.Transport.bpm.value = bpm;
  }, []);

  // ── Stop everything ─────────────────────────────────────────────────────
  const stop = useCallback(() => {
    Tone.Transport.stop();
    Tone.Transport.cancel();
    Tone.Transport.position = 0;
    birdPlayers.current.forEach((p) => {
      try {
        p.unsync();
        if (p.state === 'started') p.stop();
      } catch { /* ignore */ }
    });
    beatPlayers.current.forEach((p) => {
      try {
        p.unsync();
        if (p.state === 'started') p.stop();
      } catch { /* ignore */ }
    });
    setIsPlaying(false);
  }, []);

  // ── Play the current timeline ───────────────────────────────────────────
  const play = useCallback(async (tracks, beatId, bpm) => {
    await ensureStarted();

    // Reset transport + any prior scheduling.
    Tone.Transport.stop();
    Tone.Transport.cancel();
    Tone.Transport.position = 0;
    Tone.Transport.bpm.value = bpm;

    // Reset bird players to a clean state.
    birdPlayers.current.forEach((p) => {
      try {
        p.unsync();
        if (p.state === 'started') p.stop();
        p.volume.value = 0;
      } catch { /* ignore */ }
    });

    // Schedule each brick. startTime = slotIndex * SLOT_SECONDS.
    tracks.forEach((track) => {
      if (track.muted) return; // muted track: skip scheduling its bricks
      const db = linearToDb(track.volume);
      Object.entries(track.bricks).forEach(([slot, brick]) => {
        const player = birdPlayers.current.get(brick.birdId);
        if (!player) return;
        const startTime = Number(slot) * SLOT_SECONDS;
        player.volume.value = db;
        // sync().start(offset) schedules along the Transport timeline.
        player.sync().start(startTime);
      });
    });

    // Beat loop from transport time 0.
    if (beatId && beatId !== 'none') {
      const beatPlayer = beatPlayers.current.get(beatId);
      if (beatPlayer) {
        beatPlayer.unsync();
        beatPlayer.sync().start(0);
      }
    }

    Tone.Transport.start();
    setIsPlaying(true);
  }, [ensureStarted]);

  // ── Preview one bird clip (independent of Transport) ────────────────────
  const previewBird = useCallback(async (birdId) => {
    await ensureStarted();
    const player = birdPlayers.current.get(birdId);
    if (!player) return;
    try {
      player.unsync();
      if (player.state === 'started') player.stop();
      player.volume.value = -15; // low volume preview
      player.start();
    } catch (err) {
      console.error('preview failed', err);
    }
  }, [ensureStarted]);

  // ── Preview one beat loop briefly (independent of Transport) ────────────
  const previewBeat = useCallback(async (beatId) => {
    await ensureStarted();
    const player = beatPlayers.current.get(beatId);
    if (!player) return;
    try {
      player.unsync();
      if (player.state === 'started') player.stop();
      player.volume.value = -10;
      player.start();
      // stop after one ~8s loop so preview doesn't run forever
      player.stop('+8');
    } catch (err) {
      console.error('beat preview failed', err);
    }
  }, [ensureStarted]);

  return {
    loading,
    isPlaying,
    manifest,
    play,
    stop,
    setBpm,
    previewBird,
    previewBeat,
  };
}
