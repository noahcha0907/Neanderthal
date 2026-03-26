import { useEffect, useMemo, useRef, useState } from 'react';
import { GooeyText } from './ui/gooey-text-morphing';

export interface ArtworkItem {
  artwork_id: string;
  svg_content: string;
  created_at: string;
  trace_text: string;
}

interface Props {
  artworks: ArtworkItem[];
  isOpen: boolean;
}

const COMPOSING_WORDS = [
  'composing', 'justifying', 'creating', 'pondering', 'experiencing',
  'understanding', 'connecting', 'poetry', 'literature', 'reading',
  'studying', 'learning', 'empathizing', 'leaping', 'logicalizing',
];

export function ArtworkPanel({ artworks, isOpen }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [detailId, setDetailId] = useState<string | null>(null);

  // Pick a new random start offset each time a generation completes
  const [startOffset, setStartOffset] = useState(0);
  const prevCount = useRef(0);
  useEffect(() => {
    if (artworks.length > prevCount.current) {
      setStartOffset(Math.floor(Math.random() * COMPOSING_WORDS.length));
    }
    prevCount.current = artworks.length;
  }, [artworks.length]);

  // Rotate the word list so cycling begins at the chosen offset
  const cyclingWords = useMemo(() => {
    const i = startOffset % COMPOSING_WORDS.length;
    return [...COMPOSING_WORDS.slice(i), ...COMPOSING_WORDS.slice(0, i)];
  }, [startOffset]);

  // Auto-scroll to bottom as new artworks arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [artworks.length]);

  return (
    <>
      {/* Panel — fixed overlay on the right, does NOT push the graph */}
      <div style={{
        position: 'fixed',
        top: 0,
        right: 0,
        width: 300,
        height: '100vh',
        background: 'rgba(255,255,255,0.04)',
        backdropFilter: 'blur(40px) saturate(1.8)',
        WebkitBackdropFilter: 'blur(40px) saturate(1.8)',
        borderLeft: '1px solid rgba(255,255,255,0.09)',
        boxShadow: '-12px 0 48px rgba(0,0,0,0.4), inset 1px 0 0 rgba(255,255,255,0.06)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 200,
        transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)',
        pointerEvents: isOpen ? 'auto' : 'none',
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 16px 12px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          flexShrink: 0,
        }}>
          <GooeyText
            texts={cyclingWords}
            morphTime={1.3}
            cooldownTime={0.5}
            align="left"
            style={{ width: '100%', height: 32, marginBottom: 4 }}
            textStyle={{
              fontSize: 22,
              fontWeight: 700,
              fontFamily: "'SF Mono', ui-monospace, monospace",
              color: '#e2e8f0',
              letterSpacing: '-0.02em',
              whiteSpace: 'nowrap',
            }}
          />
          <div style={{ color: '#475569', fontSize: 11, fontFamily: "'SF Mono', ui-monospace, monospace", marginTop: 3 }}>
            {artworks.length === 0
              ? 'Waiting for first generation…'
              : `${artworks.length} artwork${artworks.length !== 1 ? 's' : ''} this session`}
          </div>
        </div>

        {/* Scrollable grid */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: 12,
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 10,
            alignContent: 'start',
          }}
        >
          {artworks.length === 0 && (
            <div style={{
              gridColumn: '1 / -1',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              paddingTop: 48,
              opacity: 0.3,
            }}>
              <div style={{ fontSize: 28, color: '#64748b' }}>◎</div>
            </div>
          )}

          {artworks.map((a) => (
            <ArtworkCard
              key={a.artwork_id}
              artwork={a}
              onClick={() => setDetailId(a.artwork_id)}
            />
          ))}

        </div>
      </div>

      {/* Detail overlay — shown when a card is clicked */}
      {detailId && (() => {
        const item = artworks.find(a => a.artwork_id === detailId);
        return item ? (
          <ArtworkDetailOverlay item={item} onClose={() => setDetailId(null)} />
        ) : null;
      })()}
    </>
  );
}

function ArtworkCard({ artwork, onClick }: { artwork: ArtworkItem; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: 8,
        overflow: 'hidden',
        cursor: 'pointer',
        padding: 0,
        textAlign: 'left',
        animation: 'artworkSlideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(99,102,241,0.5)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)')}
    >
      {/* SVG thumbnail — artwork-thumb CSS forces inner svg to fill the box */}
      <div
        className="artwork-thumb"
        style={{ width: '100%', aspectRatio: '1', background: '#000000', overflow: 'hidden' }}
        dangerouslySetInnerHTML={{ __html: artwork.svg_content }}
      />
      <div style={{
        padding: '4px 6px',
        color: '#475569',
        fontSize: 9,
        fontFamily: 'monospace',
        letterSpacing: 0.2,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}>
        {artwork.artwork_id}
      </div>
    </button>
  );
}

function ArtworkDetailOverlay({ item, onClose }: { item: ArtworkItem; onClose: () => void }) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.55)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        zIndex: 2000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'rgba(255,255,255,0.05)',
          backdropFilter: 'blur(40px) saturate(1.8)',
          WebkitBackdropFilter: 'blur(40px) saturate(1.8)',
          border: '1px solid rgba(255,255,255,0.12)',
          boxShadow: '0 32px 80px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.09)',
          borderRadius: 20,
          maxWidth: 820,
          width: '100%',
          maxHeight: '90vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Modal header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '14px 20px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          flexShrink: 0,
        }}>
          <span style={{ color: 'rgba(148,163,184,0.65)', fontSize: 11, fontFamily: "'SF Mono', ui-monospace, monospace", letterSpacing: '0.02em' }}>{item.artwork_id}</span>
          <button
            onClick={onClose}
            style={{
              background: 'rgba(255,255,255,0.07)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 999,
              color: 'rgba(255,255,255,0.5)',
              cursor: 'pointer',
              fontSize: 16,
              lineHeight: 1,
              width: 28,
              height: 28,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            ×
          </button>
        </div>

        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* SVG display */}
          <div style={{
            width: 340,
            flexShrink: 0,
            background: 'rgba(0,0,0,0.3)',
            borderRight: '1px solid rgba(255,255,255,0.07)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}>
            <div
              className="artwork-detail"
              style={{ width: '100%', aspectRatio: '1', overflow: 'hidden', borderRadius: 4 }}
              dangerouslySetInnerHTML={{ __html: item.svg_content }}
            />
          </div>

          {/* Justification trace */}
          <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
            <div style={{
              color: 'rgba(100,116,139,0.7)',
              fontSize: 10,
              fontFamily: "'SF Mono', ui-monospace, monospace",
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              marginBottom: 12,
            }}>
              Justification trace
            </div>
            {item.trace_text ? (
              <pre style={{
                margin: 0,
                color: 'rgba(203,213,225,0.85)',
                fontSize: 12,
                fontFamily: "'SF Mono', ui-monospace, monospace",
                lineHeight: 1.7,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {item.trace_text}
              </pre>
            ) : (
              <p style={{ color: 'rgba(71,85,105,0.8)', fontSize: 12, fontFamily: "'SF Mono', ui-monospace, monospace", fontStyle: 'italic' }}>
                No trace recorded for this artwork.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
