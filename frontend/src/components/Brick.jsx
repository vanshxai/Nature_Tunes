import { useEffect, useState } from 'react';
import { roleColor } from '../utils/audioUtils';

/**
 * A placed bird on the timeline. Clicking once arms a "click again to remove"
 * confirmation; clicking again removes it. Clicking elsewhere cancels.
 */
export default function Brick({ bird, onRemove }) {
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!confirming) return undefined;
    const t = setTimeout(() => setConfirming(false), 2000);
    return () => clearTimeout(t);
  }, [confirming]);

  const handleClick = (e) => {
    e.stopPropagation();
    if (confirming) {
      onRemove();
    } else {
      setConfirming(true);
    }
  };

  const name = bird ? bird.common_name : 'Unknown';
  const role = bird ? bird.suggested_role : 'melody';

  return (
    <div
      className="brick"
      style={{ background: roleColor(role) }}
      onClick={handleClick}
      title="Click to remove"
    >
      <span className="brick-name">{name}</span>
      <span className="brick-wave">〰️</span>
      {confirming && (
        <div className="brick-confirm">click again to remove</div>
      )}
    </div>
  );
}
