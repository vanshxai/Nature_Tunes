const BEATS = [
  { id: 'none', name: 'None' },
  { id: 'soft', name: 'Soft' },
  { id: 'tribal', name: 'Tribal' },
  { id: 'electronic', name: 'Electronic' },
];

export default function BeatControls({ selectedBeat, onSelectBeat, bpm, onBpmChange }) {
  return (
    <section className="beat-controls">
      <span className="beat-controls-label">Beat Pattern:</span>
      <div className="beat-pills">
        {BEATS.map((beat) => (
          <button
            key={beat.id}
            className={`beat-pill ${selectedBeat === beat.id ? 'active' : ''}`}
            onClick={() => onSelectBeat(beat.id)}
          >
            {beat.name}
          </button>
        ))}
      </div>

      <div className="bpm-control">
        <label htmlFor="bpm">BPM</label>
        <input
          id="bpm"
          type="range"
          min="40"
          max="140"
          step="1"
          value={bpm}
          onChange={(e) => onBpmChange(Number(e.target.value))}
        />
        <span className="bpm-value">{bpm} BPM</span>
      </div>
    </section>
  );
}
