import { useDrop } from 'react-dnd';
import { NUM_SLOTS } from '../utils/audioUtils';
import { BIRD_DND_TYPE } from './BirdCard';
import Brick from './Brick';

function Slot({ trackId, slotIndex, brick, birdsById, onDropBird, onRemoveBrick }) {
  const [{ isOver }, drop] = useDrop(
    () => ({
      accept: BIRD_DND_TYPE,
      drop: (item) => onDropBird(trackId, slotIndex, item.birdId),
      collect: (monitor) => ({ isOver: monitor.isOver() }),
    }),
    [trackId, slotIndex, onDropBird]
  );

  return (
    <div ref={drop} className={`slot ${isOver ? 'drag-over' : ''}`}>
      {brick && (
        <Brick
          bird={birdsById[brick.birdId]}
          onRemove={() => onRemoveBrick(trackId, slotIndex)}
        />
      )}
    </div>
  );
}

export default function Track({
  track,
  index,
  birdsById,
  canDelete,
  onDropBird,
  onRemoveBrick,
  onDeleteTrack,
  onVolumeChange,
  onToggleMute,
}) {
  return (
    <div className="track">
      <div className="track-controls">
        <div className="track-controls-top">
          <span className="track-number">Track {index + 1}</span>
          <button
            className="track-delete"
            onClick={() => onDeleteTrack(track.id)}
            disabled={!canDelete}
            title="Delete track"
          >
            ✕
          </button>
        </div>
        <div className="track-volume">
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={track.volume}
            onChange={(e) => onVolumeChange(track.id, Number(e.target.value))}
            title={`Volume ${Math.round(track.volume * 100)}%`}
          />
          <button
            className={`track-mute ${track.muted ? 'muted' : ''}`}
            onClick={() => onToggleMute(track.id)}
            title={track.muted ? 'Unmute' : 'Mute'}
          >
            {track.muted ? 'Muted' : 'Mute'}
          </button>
        </div>
      </div>

      <div className="track-dropzone">
        {Array.from({ length: NUM_SLOTS }, (_, slotIndex) => (
          <Slot
            key={slotIndex}
            trackId={track.id}
            slotIndex={slotIndex}
            brick={track.bricks[slotIndex]}
            birdsById={birdsById}
            onDropBird={onDropBird}
            onRemoveBrick={onRemoveBrick}
          />
        ))}
      </div>
    </div>
  );
}
