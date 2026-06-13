import { useEffect } from 'react';
import { useDrag } from 'react-dnd';
import { getEmptyImage } from 'react-dnd-html5-backend';

export const BIRD_DND_TYPE = 'BIRD';

const ROLE_LABEL = { melody: 'Melody', texture: 'Texture', anchor: 'Anchor' };

export default function BirdCard({ bird, onPreview }) {
  const [{ isDragging }, drag, dragPreview] = useDrag(
    () => ({
      type: BIRD_DND_TYPE,
      item: { birdId: bird.id, role: bird.suggested_role, name: bird.common_name },
      collect: (monitor) => ({ isDragging: monitor.isDragging() }),
    }),
    [bird.id]
  );

  // Use a custom (text) drag preview rather than the default DOM snapshot.
  useEffect(() => {
    dragPreview(getEmptyImage(), { captureDraggingState: true });
  }, [dragPreview]);

  const handlePreview = (e) => {
    e.stopPropagation();
    onPreview(bird.id);
  };

  return (
    <div
      ref={drag}
      className={`bird-card ${isDragging ? 'dragging' : ''}`}
      title={`Drag ${bird.common_name} onto the timeline`}
    >
      <button className="preview-btn" onClick={handlePreview} title="Preview">▶</button>
      <span className="bird-card-name">{bird.common_name}</span>
      <div className="bird-card-meta">
        <span className={`role-badge ${bird.suggested_role}`}>
          {ROLE_LABEL[bird.suggested_role] || bird.suggested_role}
        </span>
        <span className="bird-card-freq">{Math.round(bird.dominant_freq_hz)} Hz</span>
      </div>
    </div>
  );
}
