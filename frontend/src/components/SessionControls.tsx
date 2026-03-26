import type { SessionControls as SessionControlsType } from '../hooks/useSession';

interface Props {
  session: SessionControlsType;
}

export function SessionControls({ session }: Props) {
  const { state, error } = session;

  if (!state.isActive && !error) return null;

  return (
    <div style={{
      position: 'fixed',
      bottom: 28,
      left: 24,
      zIndex: 100,
      userSelect: 'none',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      padding: '6px 8px',
      borderRadius: 0,
      background: 'rgba(255,255,255,0.04)',
      backdropFilter: 'blur(20px) saturate(1.5)',
      WebkitBackdropFilter: 'blur(20px) saturate(1.5)',
      border: '1px solid rgba(255,255,255,0.09)',
      boxShadow: '0 8px 40px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.07)',
    }}>
      {/* Artwork counter */}
      {state.isActive && (
        <span style={{
          color: 'rgba(148,163,184,0.7)',
          fontSize: 12,
          fontFamily: "'SF Mono', ui-monospace, monospace",
          minWidth: 60,
        }}>
          {state.artworkCount} artwork{state.artworkCount !== 1 ? 's' : ''}
        </span>
      )}

      {/* Error */}
      {error && (
        <span style={{ color: '#f87171', fontSize: 12, maxWidth: 200, fontFamily: "'SF Mono', ui-monospace, monospace" }}>
          {error}
        </span>
      )}
    </div>
  );
}
