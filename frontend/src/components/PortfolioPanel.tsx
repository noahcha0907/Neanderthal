import { useEffect, useState } from 'react';
import { fetchPortfolio, fetchPortfolioItem } from '../api/client';

export interface PortfolioItem {
  artwork_id: string;
  created_at: string;
}

export interface PortfolioDetail extends PortfolioItem {
  svg_content: string;
  trace_text: string;
  voter_ids: string[];
}

// ── Portfolio content grid ────────────────────────────────────────────────────
// Rendered inside the floating panel popover body.

interface PortfolioContentProps {
  onDetailSelect: (detail: PortfolioDetail) => void;
}

export function PortfolioContent({ onDetailSelect }: PortfolioContentProps) {
  const [items, setItems] = useState<PortfolioItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchPortfolio()
      .then(data => setItems([...data].reverse()))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleCardClick = async (artworkId: string) => {
    const detail = await fetchPortfolioItem(artworkId).catch(() => null);
    if (detail) onDetailSelect(detail);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', maxHeight: '72vh' }}>
      {/* Header */}
      <div style={{
        padding: '14px 16px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        flexShrink: 0,
      }}>
        <div style={{
          color: '#e2e8f0', fontSize: 13, fontWeight: 700,
          fontFamily: "'SF Mono', ui-monospace, monospace", letterSpacing: 0.3,
        }}>
          Public portfolio
        </div>
        <div style={{ color: '#475569', fontSize: 11, fontFamily: "'SF Mono', ui-monospace, monospace", marginTop: 3 }}>
          {loading
            ? 'Loading…'
            : items.length === 0
              ? 'No artworks yet'
              : `${items.length} artwork${items.length !== 1 ? 's' : ''}`}
        </div>
      </div>

      {/* Scrollable grid */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: 12,
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 20,
        alignContent: 'start',
      }}>
        {!loading && items.length === 0 && (
          <div style={{
            gridColumn: '1 / -1',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            paddingTop: 40,
            gap: 10,
            opacity: 0.35,
          }}>
            <div style={{ fontSize: 28 }}>◎</div>
            <div style={{
              color: '#64748b', fontSize: 12,
              fontFamily: "'SF Mono', ui-monospace, monospace", textAlign: 'center',
            }}>
              Generated artworks will appear here
            </div>
          </div>
        )}

        {items.map(item => (
          <PortfolioCard
            key={item.artwork_id}
            item={item}
            onClick={() => handleCardClick(item.artwork_id)}
          />
        ))}
      </div>
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────

function PortfolioCard({ item, onClick }: { item: PortfolioItem; onClick: () => void }) {
  const [svgContent, setSvgContent] = useState<string | null>(null);

  useEffect(() => {
    fetchPortfolioItem(item.artwork_id)
      .then(d => setSvgContent(d.svg_content))
      .catch(() => {});
  }, [item.artwork_id]);

  const date = item.created_at
    ? new Date(item.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : '';

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
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(99,102,241,0.5)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)')}
    >
      <div style={{
        width: '100%',
        aspectRatio: '1',
        background: '#000000',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        {svgContent
          ? <div style={{ width: '100%', height: '100%' }} dangerouslySetInnerHTML={{ __html: svgContent }} />
          : <div style={{ width: 20, height: 20, borderRadius: '50%', background: 'rgba(255,255,255,0.06)' }} />}
      </div>
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
        {date || item.artwork_id}
      </div>
    </button>
  );
}

// ── Detail overlay ────────────────────────────────────────────────────────────
// Full-screen overlay rendered at the App level.

interface PortfolioDetailOverlayProps {
  detail: PortfolioDetail;
  onClose: () => void;
  onNodeSelect?: (nodeId: string) => void;
}

export function PortfolioDetailOverlay({ detail, onClose, onNodeSelect }: PortfolioDetailOverlayProps) {
  const handleDownload = () => {
    const blob = new Blob([detail.svg_content], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${detail.artwork_id}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const date = detail.created_at
    ? new Date(detail.created_at).toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : '';

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.75)',
        backdropFilter: 'blur(6px)',
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
          background: '#000000',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 16,
          maxWidth: 860,
          width: '100%',
          maxHeight: '90vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px 20px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          flexShrink: 0,
          gap: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
            <span style={{ color: '#94a3b8', fontSize: 12, fontFamily: 'monospace', flexShrink: 0 }}>
              {detail.artwork_id}
            </span>
            {date && (
              <span style={{ color: '#475569', fontSize: 11, fontFamily: "'SF Mono', ui-monospace, monospace" }}>{date}</span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <button
              onClick={handleDownload}
              style={{
                background: 'rgba(99,102,241,0.15)',
                border: '1px solid rgba(99,102,241,0.4)',
                borderRadius: 6,
                color: '#a5b4fc',
                fontSize: 12,
                fontFamily: "'SF Mono', ui-monospace, monospace",
                cursor: 'pointer',
                padding: '4px 10px',
              }}
            >
              ↓ Download SVG
            </button>
            <button
              onClick={onClose}
              style={{
                background: 'none', border: 'none', color: '#64748b',
                cursor: 'pointer', fontSize: 20, lineHeight: 1, padding: '0 4px',
              }}
            >
              ×
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* SVG */}
          <div style={{
            width: 340,
            flexShrink: 0,
            background: '#000000',
            borderRight: '1px solid rgba(255,255,255,0.07)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}>
            <div
              className="artwork-detail"
              style={{ width: '100%', aspectRatio: '1', overflow: 'hidden' }}
              dangerouslySetInnerHTML={{ __html: detail.svg_content }}
            />
          </div>

          {/* Right column: source nodes + trace */}
          <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 20 }}>
            {(detail.voter_ids ?? []).length > 0 && (
              <div>
                <div style={{
                  color: '#64748b', fontSize: 10, fontFamily: "'SF Mono', ui-monospace, monospace",
                  letterSpacing: 1, textTransform: 'uppercase', marginBottom: 8,
                }}>
                  Source nodes
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {(detail.voter_ids ?? []).map(id => (
                    <button
                      key={id}
                      onClick={() => onNodeSelect?.(id)}
                      style={{
                        background: 'rgba(255,255,255,0.03)',
                        border: '1px solid rgba(255,255,255,0.07)',
                        borderRadius: 5,
                        color: '#94a3b8',
                        fontSize: 11,
                        fontFamily: 'monospace',
                        cursor: onNodeSelect ? 'pointer' : 'default',
                        padding: '4px 8px',
                        textAlign: 'left',
                        transition: 'border-color 0.15s, color 0.15s',
                      }}
                      onMouseEnter={e => {
                        if (onNodeSelect) {
                          e.currentTarget.style.borderColor = 'rgba(99,102,241,0.4)';
                          e.currentTarget.style.color = '#c7d2fe';
                        }
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)';
                        e.currentTarget.style.color = '#94a3b8';
                      }}
                    >
                      {id}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div>
              <div style={{
                color: '#64748b', fontSize: 10, fontFamily: "'SF Mono', ui-monospace, monospace",
                letterSpacing: 1, textTransform: 'uppercase', marginBottom: 12,
              }}>
                Justification trace
              </div>
              {detail.trace_text ? (
                <pre style={{
                  margin: 0, color: '#cbd5e1', fontSize: 12,
                  fontFamily: 'monospace', lineHeight: 1.7,
                  whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                }}>
                  {detail.trace_text}
                </pre>
              ) : (
                <p style={{ color: '#475569', fontSize: 13, fontFamily: "'SF Mono', ui-monospace, monospace", fontStyle: 'italic', margin: 0 }}>
                  No trace recorded for this artwork.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
