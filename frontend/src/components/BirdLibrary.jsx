import BirdCard from './BirdCard';

const BEAT_CARDS = [
  { id: 'soft', name: 'Soft' },
  { id: 'tribal', name: 'Tribal' },
  { id: 'electronic', name: 'Electronic' },
];

export default function BirdLibrary({ birds, beats, onPreviewBird, onPreviewBeat }) {
  const beatList = beats && beats.length ? beats : BEAT_CARDS;

  return (
    <section className="library">
      <h2 className="library-title">Bird Library</h2>
      <p className="library-subtitle">Drag birds onto the timeline</p>

      <div className="bird-grid">
        {birds.map((bird) => (
          <BirdCard key={bird.id} bird={bird} onPreview={onPreviewBird} />
        ))}
      </div>

      <div className="beat-library">
        <h3 className="beat-library-title">Beat Patterns</h3>
        <div className="beat-card-grid">
          {beatList.map((beat) => (
            <div key={beat.id} className="beat-card">
              <button
                className="preview-btn"
                onClick={() => onPreviewBeat(beat.id)}
                title={`Preview ${beat.name}`}
              >
                ▶
              </button>
              <span className="beat-card-name">{beat.name}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
