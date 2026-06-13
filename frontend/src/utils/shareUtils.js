// Share / restore the timeline state via URL query params.
//
// URL shape:  ?seq=<base64 JSON of tracks>&beat=soft&bpm=75
//
// The encoded track data is a compact representation of placed bricks so that
// it survives a round-trip through the URL.

/**
 * Encode the timeline tracks into a compact, URL-safe base64 string.
 * Each track is reduced to its bricks: { s: slotIndex, b: birdId }.
 */
export function encodeTimeline(tracks) {
  const compact = tracks.map((track) => ({
    v: track.volume,
    m: track.muted ? 1 : 0,
    b: Object.entries(track.bricks).map(([slot, brick]) => ({
      s: Number(slot),
      id: brick.birdId,
    })),
  }));
  const json = JSON.stringify(compact);
  // btoa handles latin1; our ids are ascii so this is safe.
  return base64UrlEncode(json);
}

/**
 * Decode a base64 seq string back into the tracks array used by useTimeline.
 * Returns null on any failure (malformed param).
 */
export function decodeTimeline(seq) {
  try {
    const json = base64UrlDecode(seq);
    const compact = JSON.parse(json);
    if (!Array.isArray(compact)) return null;
    return compact.map((t, idx) => {
      const bricks = {};
      (t.b || []).forEach(({ s, id }) => {
        bricks[s] = { birdId: id };
      });
      return {
        id: idx + 1,
        volume: typeof t.v === 'number' ? t.v : 0.8,
        muted: !!t.m,
        bricks,
      };
    });
  } catch {
    return null;
  }
}

/** Build a full share URL from the current state. */
export function buildShareUrl(tracks, beat, bpm) {
  const params = new URLSearchParams();
  params.set('seq', encodeTimeline(tracks));
  if (beat && beat !== 'none') params.set('beat', beat);
  params.set('bpm', String(bpm));
  return `${window.location.origin}${window.location.pathname}?${params.toString()}`;
}

/** Parse the current window location for shared state. Returns {tracks, beat, bpm} or null. */
export function parseShareUrl() {
  const params = new URLSearchParams(window.location.search);
  const seq = params.get('seq');
  if (!seq) return null;
  const tracks = decodeTimeline(seq);
  if (!tracks) return null;
  const beat = params.get('beat') || 'none';
  const bpm = Number(params.get('bpm')) || 75;
  return { tracks, beat, bpm };
}

/** Copy text to clipboard, with a fallback for non-secure contexts. */
export async function copyToClipboard(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to legacy path */
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    return true;
  } catch {
    return false;
  }
}

// ── base64 url-safe helpers ──────────────────────────────────────────────
function base64UrlEncode(str) {
  return btoa(unescape(encodeURIComponent(str)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

function base64UrlDecode(b64) {
  const padded = b64.replace(/-/g, '+').replace(/_/g, '/');
  return decodeURIComponent(escape(atob(padded)));
}
