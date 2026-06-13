export default function Header({ isPlaying, onPlayStop, onShare, onOpenAdmin }) {
  return (
    <header className="header">
      <div className="header-brand">
        <div className="header-logo">🌿 NatureTunes</div>
        <div className="header-tagline">Music from nature.</div>
      </div>

      <div className="header-actions">
        <button className="btn" onClick={onOpenAdmin} title="Admin">
          🔒 Admin
        </button>
        <button className="btn" onClick={onShare} title="Share this composition">
          🔗 Share
        </button>
        <button
          className="btn btn-accent btn-play"
          onClick={onPlayStop}
          title={isPlaying ? 'Stop' : 'Play'}
        >
          {isPlaying ? '■ Stop' : '▶ Play'}
        </button>
      </div>
    </header>
  );
}
