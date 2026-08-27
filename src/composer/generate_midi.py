"""
generate_midi.py — Simple 16-bar MIDI composition in D minor at 45 BPM.

D minor scale: D, E, F, G, A, Bb, C
Melodic phrase uses: D4, F4, A4, C5 with variation across 16 bars.
"""

from pathlib import Path
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

# ── constants ─────────────────────────────────────────────────────────────────
BPM       = 45
TEMPO     = mido.bpm2tempo(BPM)   # microseconds per beat
TICKS_PPQ = 480                    # ticks per quarter note

# D minor scale MIDI notes (octave 4)
D4, E4, F4, G4, A4, Bb4, C5, D5 = 62, 64, 65, 67, 69, 70, 72, 74

# Output
OUT_PATH = Path(__file__).parent.parent.parent / "output" / "midi_test" / "test_composition.mid"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── phrase building ───────────────────────────────────────────────────────────
# Each "note" = (midi_pitch, duration_in_ticks, velocity)
Q  = TICKS_PPQ          # quarter note
H  = TICKS_PPQ * 2      # half note
E  = TICKS_PPQ // 2     # eighth note
DQ = TICKS_PPQ + E      # dotted quarter

# 8 bars of base material — 2 complementary phrases
PHRASE_A = [
    (D4,  Q,   72),
    (F4,  Q,   68),
    (A4,  H,   75),
    (C5,  Q,   70),
    (A4,  Q,   65),
    (F4,  H,   68),
    (G4,  Q,   70),
    (A4,  Q,   72),
    (D4,  H,   65),
]

PHRASE_B = [
    (A4,  Q,   70),
    (C5,  Q,   75),
    (Bb4, Q,   68),
    (A4,  Q,   72),
    (G4,  H,   65),
    (F4,  Q,   68),
    (E4,  Q,   60),
    (D4,  H,   75),
    (D4,  H,   55),   # long resolved close
]

# Variation — rhythmically displaced
PHRASE_A_VAR = [
    (D4,  E,   65),
    (F4,  E,   68),
    (A4,  Q,   75),
    (C5,  E,   72),
    (Bb4, E,   68),
    (A4,  Q,   70),
    (G4,  E,   65),
    (A4,  E,   70),
    (D5,  H,   78),
    (C5,  Q,   72),
]

PHRASE_B_VAR = [
    (C5,  Q,   72),
    (A4,  Q,   68),
    (F4,  DQ,  65),
    (G4,  E,   60),
    (A4,  H,   70),
    (D4,  Q,   55),
    (F4,  Q,   65),
    (D4,  H,   75),
]

# 16-bar structure: A A B A_var B_var A B A
SECTIONS = [
    PHRASE_A,
    PHRASE_A,
    PHRASE_B,
    PHRASE_A_VAR,
    PHRASE_B_VAR,
    PHRASE_A,
    PHRASE_B,
    PHRASE_A,
]

# ── build MIDI ────────────────────────────────────────────────────────────────
mid   = MidiFile(ticks_per_beat=TICKS_PPQ)
track = MidiTrack()
mid.tracks.append(track)

# Metadata
track.append(MetaMessage("set_tempo",  tempo=TEMPO,         time=0))
track.append(MetaMessage("key_signature", key="Dm",         time=0))
track.append(MetaMessage("time_signature",
                          numerator=4, denominator=4,
                          clocks_per_click=24,
                          notated_32nd_notes_per_beat=8,   time=0))
track.append(MetaMessage("track_name", name="D Minor Melody", time=0))

# Program change — flute (GM #74)
track.append(Message("program_change", channel=0, program=73, time=0))

for phrase in SECTIONS:
    for pitch, duration, vel in phrase:
        track.append(Message("note_on",  channel=0, note=pitch, velocity=vel,       time=0))
        track.append(Message("note_off", channel=0, note=pitch, velocity=0,          time=duration))

track.append(MetaMessage("end_of_track", time=0))

mid.save(str(OUT_PATH))

total_ticks = sum(dur for phrase in SECTIONS for _, dur, _ in phrase)
total_beats = total_ticks / TICKS_PPQ
total_secs  = total_beats * (60 / BPM)
print(f"[OK]  Saved: {OUT_PATH}")
print(f"      {len(SECTIONS)} sections, {total_beats:.1f} beats, ~{total_secs:.0f}s at {BPM} BPM")
