// Audio helper utilities.

export const SLOT_SECONDS = 20;
export const NUM_SLOTS = 6; // 120s total
export const TOTAL_SECONDS = SLOT_SECONDS * NUM_SLOTS;

/**
 * Convert a linear 0..1 volume into a Tone.js dB value in the range -40..0.
 * 0   -> -40 dB (effectively silent-ish)
 * 1   ->   0 dB (full)
 */
export function linearToDb(linear) {
  const v = Math.max(0, Math.min(1, linear));
  return -40 + v * 40;
}

/** Brick background colour by suggested role. */
export function roleColor(role) {
  switch (role) {
    case 'melody':
      return 'var(--role-melody)';
    case 'texture':
      return 'var(--role-texture)';
    case 'anchor':
      return 'var(--role-anchor)';
    default:
      return 'var(--card)';
  }
}
