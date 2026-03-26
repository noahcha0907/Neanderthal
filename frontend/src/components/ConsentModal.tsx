import { useState } from 'react';

interface Props {
  artworkCount: number;
  hadUploads: boolean;
  onSubmit: (artworkConsent: boolean, documentConsent: boolean) => Promise<void>;
  onDismiss: () => void; // called immediately when any button is pressed, before the API call
}

export function ConsentModal({ artworkCount, hadUploads, onSubmit, onDismiss }: Props) {
  const [artworkConsent, setArtworkConsent] = useState(false);
  const [documentConsent, setDocumentConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (artConsent: boolean, docConsent: boolean) => {
    if (submitting) return;
    setSubmitting(true);
    onDismiss(); // close immediately — API runs in background
    try {
      await onSubmit(artConsent, docConsent);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0,0,0,0.55)',
      backdropFilter: 'blur(8px)',
      WebkitBackdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 2000,
    }}>
      <div style={{
        background: 'rgba(255,255,255,0.05)',
        backdropFilter: 'blur(40px) saturate(1.8)',
        WebkitBackdropFilter: 'blur(40px) saturate(1.8)',
        border: '1px solid rgba(255,255,255,0.12)',
        boxShadow: '0 24px 64px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.09)',
        borderRadius: 20,
        padding: 32,
        maxWidth: 420,
        width: '90%',
        color: '#e2e8f0',
        fontFamily: "'SF Mono', ui-monospace, monospace",
      }}>
        <h2 style={{ margin: '0 0 8px', fontSize: 17, fontWeight: 700, letterSpacing: '-0.01em' }}>
          Session complete
        </h2>
        <p style={{ margin: '0 0 24px', color: 'rgba(148,163,184,0.7)', fontSize: 12, lineHeight: 1.6 }}>
          {artworkCount > 0
            ? `The robot made ${artworkCount} artwork${artworkCount !== 1 ? 's' : ''} during your session.`
            : 'No artworks were generated during your session.'}
          {' '}Decide what to share with the public corpus.
        </p>

        {artworkCount > 0 && (
          <label style={{
            display: 'flex', gap: 12, alignItems: 'flex-start', marginBottom: 14,
            cursor: submitting ? 'default' : 'pointer',
            background: artworkConsent ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.02)',
            border: `1px solid ${artworkConsent ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.07)'}`,
            borderRadius: 12,
            padding: '12px 14px',
            transition: 'background 0.15s, border-color 0.15s',
          }}>
            <input
              type="checkbox"
              checked={artworkConsent}
              disabled={submitting}
              onChange={e => setArtworkConsent(e.target.checked)}
              style={{ marginTop: 2, accentColor: '#818cf8', width: 15, height: 15, flexShrink: 0 }}
            />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3, color: '#e2e8f0' }}>Share artworks</div>
              <div style={{ fontSize: 11, color: 'rgba(148,163,184,0.65)', lineHeight: 1.55 }}>
                Adds the artworks generated this session to the public portfolio and the robot's permanent memory.
              </div>
            </div>
          </label>
        )}

        {hadUploads && (
          <label style={{
            display: 'flex', gap: 12, alignItems: 'flex-start', marginBottom: 14,
            cursor: submitting ? 'default' : 'pointer',
            background: documentConsent ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.02)',
            border: `1px solid ${documentConsent ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.07)'}`,
            borderRadius: 12,
            padding: '12px 14px',
            transition: 'background 0.15s, border-color 0.15s',
          }}>
            <input
              type="checkbox"
              checked={documentConsent}
              disabled={submitting}
              onChange={e => setDocumentConsent(e.target.checked)}
              style={{ marginTop: 2, accentColor: '#818cf8', width: 15, height: 15, flexShrink: 0 }}
            />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3, color: '#e2e8f0' }}>Share uploaded documents</div>
              <div style={{ fontSize: 11, color: 'rgba(148,163,184,0.65)', lineHeight: 1.55 }}>
                Adds your uploaded text to the shared corpus so the robot can draw from it in future sessions.
              </div>
            </div>
          </label>
        )}

        <div style={{ display: 'flex', gap: 8, marginTop: 24 }}>
          <button
            onClick={() => handleSubmit(false, false)}
            disabled={submitting}
            style={{
              flex: 1,
              padding: '9px 0',
              background: 'rgba(255,255,255,0.06)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 999,
              color: submitting ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.55)',
              fontSize: 12,
              fontFamily: "'SF Mono', ui-monospace, monospace",
              fontWeight: 600,
              cursor: submitting ? 'default' : 'pointer',
              opacity: submitting ? 0.5 : 1,
              boxShadow: '0 2px 12px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.08)',
              transition: 'background 0.15s, border-color 0.15s',
            }}
          >
            Share nothing
          </button>
          <button
            onClick={() => handleSubmit(artworkConsent, documentConsent)}
            disabled={submitting}
            style={{
              flex: 1,
              padding: '9px 0',
              background: submitting
                ? 'rgba(99,102,241,0.25)'
                : 'linear-gradient(145deg, rgba(129,140,248,0.55) 0%, rgba(99,102,241,0.35) 100%)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1px solid rgba(129,140,248,0.45)',
              borderRadius: 999,
              color: submitting ? 'rgba(255,255,255,0.35)' : '#fff',
              fontSize: 12,
              fontFamily: "'SF Mono', ui-monospace, monospace",
              fontWeight: 700,
              cursor: submitting ? 'default' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              boxShadow: '0 2px 16px rgba(99,102,241,0.3), inset 0 1px 0 rgba(255,255,255,0.18)',
              transition: 'background 0.15s, border-color 0.15s, opacity 0.15s',
            }}
          >
            {submitting ? (
              <>
                <span style={{ fontSize: 10 }}>●</span>
                Saving…
              </>
            ) : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
}
