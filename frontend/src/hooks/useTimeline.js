import { useCallback, useState } from 'react';

const MIN_TRACKS = 1;
const MAX_TRACKS = 8;
const INITIAL_TRACKS = 4;

function makeTrack(id) {
  return { id, volume: 0.8, muted: false, bricks: {} };
}

function defaultTracks() {
  return Array.from({ length: INITIAL_TRACKS }, (_, i) => makeTrack(i + 1));
}

/**
 * Timeline state hook.
 *
 * Track shape: { id, volume (0..1), muted (bool), bricks: { [slotIndex]: { birdId } } }
 */
export function useTimeline(initial) {
  const [tracks, setTracks] = useState(() =>
    initial && initial.length ? normalizeIds(initial) : defaultTracks()
  );

  const addTrack = useCallback(() => {
    setTracks((prev) => {
      if (prev.length >= MAX_TRACKS) return prev;
      const nextId = prev.length ? Math.max(...prev.map((t) => t.id)) + 1 : 1;
      return [...prev, makeTrack(nextId)];
    });
  }, []);

  const deleteTrack = useCallback((trackId) => {
    setTracks((prev) => {
      if (prev.length <= MIN_TRACKS) return prev;
      return prev.filter((t) => t.id !== trackId);
    });
  }, []);

  const placeBrick = useCallback((trackId, slotIndex, birdId) => {
    setTracks((prev) =>
      prev.map((t) =>
        t.id === trackId
          ? { ...t, bricks: { ...t.bricks, [slotIndex]: { birdId } } }
          : t
      )
    );
  }, []);

  const removeBrick = useCallback((trackId, slotIndex) => {
    setTracks((prev) =>
      prev.map((t) => {
        if (t.id !== trackId) return t;
        const bricks = { ...t.bricks };
        delete bricks[slotIndex];
        return { ...t, bricks };
      })
    );
  }, []);

  const setVolume = useCallback((trackId, volume) => {
    setTracks((prev) =>
      prev.map((t) => (t.id === trackId ? { ...t, volume } : t))
    );
  }, []);

  const toggleMute = useCallback((trackId) => {
    setTracks((prev) =>
      prev.map((t) => (t.id === trackId ? { ...t, muted: !t.muted } : t))
    );
  }, []);

  const restoreTracks = useCallback((restored) => {
    if (restored && restored.length) setTracks(normalizeIds(restored));
  }, []);

  return {
    tracks,
    addTrack,
    deleteTrack,
    placeBrick,
    removeBrick,
    setVolume,
    toggleMute,
    restoreTracks,
    canAddTrack: tracks.length < MAX_TRACKS,
    canDeleteTrack: tracks.length > MIN_TRACKS,
  };
}

function normalizeIds(list) {
  return list.map((t, i) => ({
    id: t.id ?? i + 1,
    volume: typeof t.volume === 'number' ? t.volume : 0.8,
    muted: !!t.muted,
    bricks: t.bricks || {},
  }));
}
