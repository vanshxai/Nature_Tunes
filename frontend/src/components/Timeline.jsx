import { NUM_SLOTS, SLOT_SECONDS } from '../utils/audioUtils';
import Track from './Track';

export default function Timeline({
  tracks,
  birdsById,
  canAddTrack,
  canDeleteTrack,
  onDropBird,
  onRemoveBrick,
  onAddTrack,
  onDeleteTrack,
  onVolumeChange,
  onToggleMute,
}) {
  return (
    <section className="timeline">
      <div className="timeline-header">
        <span className="timeline-title">Timeline</span>
        <span className="library-subtitle" style={{ margin: 0 }}>
          {NUM_SLOTS * SLOT_SECONDS}s · {NUM_SLOTS} slots × {SLOT_SECONDS}s
        </span>
      </div>

      {/* Time ruler: 0s … 120s */}
      <div className="time-ruler">
        {Array.from({ length: NUM_SLOTS }, (_, i) => (
          <div key={i} className="ruler-slot">{i * SLOT_SECONDS}s</div>
        ))}
      </div>

      {tracks.map((track, index) => (
        <Track
          key={track.id}
          track={track}
          index={index}
          birdsById={birdsById}
          canDelete={canDeleteTrack}
          onDropBird={onDropBird}
          onRemoveBrick={onRemoveBrick}
          onDeleteTrack={onDeleteTrack}
          onVolumeChange={onVolumeChange}
          onToggleMute={onToggleMute}
        />
      ))}

      <button
        className="btn add-track-btn"
        onClick={onAddTrack}
        disabled={!canAddTrack}
        title={canAddTrack ? 'Add a track' : 'Maximum 8 tracks'}
      >
        + Add Track
      </button>
    </section>
  );
}
