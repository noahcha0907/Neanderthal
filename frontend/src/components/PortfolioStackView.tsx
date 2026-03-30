/**
 * PortfolioStackView — full-screen portfolio overlay with grid view.
 *
 * Inputs:  onClose callback, optional onNodeSelect for graph navigation
 * Outputs: renders over the app; transitions between grid view and artwork detail
 *
 * Flow:
 *   1. Fetches portfolio list on mount (most recent first)
 *   2. Displays artworks as a scrollable grid with lazy SVG thumbnails
 *   3. On card click: transitions to detail view
 *   4. Close/back button returns to grid or exits the overlay
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Download, Layers, Network, FileText } from 'lucide-react';
import { fetchPortfolio, fetchPortfolioItem } from '../api/client';
import type { PortfolioDetail, PortfolioItem } from './PortfolioPanel';

// ── Color utilities ───────────────────────────────────────────────────────────

function extractBgColor(svg: string): string | null {
  // Background rect is typically the first rect with a fill
  const m = svg.match(/<rect[^>]+fill="(#[0-9a-fA-F]{3,8}|[a-z]+)"[^>]*>/i);
  return m?.[1] ?? null;
}

function hexToHsl(hex: string): [number, number, number] {
  let r = 0, g = 0, b = 0;
  if (hex.length === 4) {
    r = parseInt(hex[1] + hex[1], 16);
    g = parseInt(hex[2] + hex[2], 16);
    b = parseInt(hex[3] + hex[3], 16);
  } else if (hex.length >= 7) {
    r = parseInt(hex.slice(1, 3), 16);
    g = parseInt(hex.slice(3, 5), 16);
    b = parseInt(hex.slice(5, 7), 16);
  }
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = d / (l > 0.5 ? 2 - max - min : max + min);
  let h = 0;
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
  else if (max === g) h = ((b - r) / d + 2) / 6;
  else h = ((r - g) / d + 4) / 6;
  return [h * 360, s, l];
}

interface PortfolioStackViewProps {
  onClose: () => void;
  onNodeSelect?: (nodeId: string) => void;
}

export function PortfolioStackView({ onClose, onNodeSelect }: PortfolioStackViewProps) {
  const [items, setItems] = useState<PortfolioItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDetail, setSelectedDetail] = useState<PortfolioDetail | null>(null);
  const [colorMap, setColorMap] = useState<Record<string, string>>({});
  const [sortMode, setSortMode] = useState<'recent' | 'similarity'>('recent');
  const [activeColor, setActiveColor] = useState<string | null>(null);

  useEffect(() => {
    fetchPortfolio()
      .then(list => setItems([...list].reverse()))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleColorExtracted = useCallback((id: string, color: string) => {
    setColorMap(prev => prev[id] === color ? prev : { ...prev, [id]: color });
  }, []);

  const uniqueColors = useMemo(
    () => [...new Set(Object.values(colorMap))],
    [colorMap],
  );

  const displayItems = useMemo(() => {
    let list = activeColor
      ? items.filter(item => colorMap[item.artwork_id] === activeColor)
      : [...items];
    if (sortMode === 'similarity') {
      list.sort((a, b) => {
        const [ha] = hexToHsl(colorMap[a.artwork_id] ?? '#000');
        const [hb] = hexToHsl(colorMap[b.artwork_id] ?? '#000');
        return ha - hb;
      });
    }
    return list;
  }, [items, colorMap, sortMode, activeColor]);

  const handleCardClick = async (artworkId: string) => {
    const detail = await fetchPortfolioItem(artworkId).catch(() => null);
    if (detail) setSelectedDetail(detail);
  };

  const inDetail = selectedDetail !== null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'rgba(0,0,0,0.15)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <style>{`
        @keyframes ping { 75%,100% { transform: scale(2); opacity: 0; } }
        .grid-thumb svg { width: 100%; height: 100%; display: block; }
      `}</style>

      {/* Header bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '18px 28px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {inDetail && (
            <button
              onClick={() => setSelectedDetail(null)}
              style={{
                background: 'none',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: 6,
                color: '#94a3b8',
                fontSize: 12,
                fontFamily: "'SF Mono', ui-monospace, monospace",
                cursor: 'pointer',
                padding: '4px 12px',
                marginRight: 4,
              }}
            >
              ← Back
            </button>
          )}
          <span style={{
            color: '#e2e8f0',
            fontFamily: "'SF Mono', ui-monospace, monospace",
            fontSize: 13,
            fontWeight: 700,
            letterSpacing: '0.06em',
          }}>
            PORTFOLIO
          </span>
          {!inDetail && !loading && items.length > 0 && (
            <span style={{
              color: '#475569',
              fontFamily: "'SF Mono', ui-monospace, monospace",
              fontSize: 11,
            }}>
              {items.length} artwork{items.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        <button
          onClick={onClose}
          style={{
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 8,
            color: '#94a3b8',
            fontSize: 12,
            fontFamily: "'SF Mono', ui-monospace, monospace",
            cursor: 'pointer',
            padding: '5px 14px',
            transition: 'border-color 0.15s, color 0.15s',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = 'rgba(255,255,255,0.25)';
            e.currentTarget.style.color = '#e2e8f0';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)';
            e.currentTarget.style.color = '#94a3b8';
          }}
        >
          × Close
        </button>
      </div>

      {/* Filter bar — hidden in detail view */}
      {!inDetail && !loading && items.length > 0 && (
        <FilterBar
          uniqueColors={uniqueColors}
          activeColor={activeColor}
          sortMode={sortMode}
          onColorSelect={(c: string) => setActiveColor(prev => prev === c ? null : c)}
          onSortChange={setSortMode}
        />
      )}

      {/* Body */}
      <AnimatePresence mode="wait">
        {!inDetail ? (
          <motion.div
            key="grid"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.18 }}
            style={{ flex: 1, overflowY: 'auto', padding: 28 }}
          >
            {loading ? (
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                height: 200,
                color: '#475569',
                fontFamily: "'SF Mono', ui-monospace, monospace",
                fontSize: 13,
              }}>
                Loading…
              </div>
            ) : items.length === 0 ? (
              <div style={{
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                height: 200, gap: 12, opacity: 0.5,
              }}>
                <div style={{ fontSize: 32, color: '#475569' }}>◎</div>
                <div style={{ color: '#475569', fontFamily: "'SF Mono', ui-monospace, monospace", fontSize: 13 }}>
                  No artworks yet
                </div>
              </div>
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                gap: 16,
              }}>
                {displayItems.map(item => (
                  <GridCard
                    key={item.artwork_id}
                    item={item}
                    onClick={() => handleCardClick(item.artwork_id)}
                    onColorExtracted={handleColorExtracted}
                  />
                ))}
              </div>
            )}
          </motion.div>
        ) : (
          <motion.div
            key="detail"
            initial={{ opacity: 0, scale: 0.94 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.94 }}
            transition={{ type: 'spring', stiffness: 260, damping: 26 }}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 28,
              overflowY: 'auto',
            }}
          >
            <ArtworkDetailView
              detail={selectedDetail}
              onNodeSelect={onNodeSelect}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Filter bar ────────────────────────────────────────────────────────────────

function FilterBar({
  uniqueColors,
  activeColor,
  sortMode,
  onColorSelect,
  onSortChange,
}: {
  uniqueColors: string[];
  activeColor: string | null;
  sortMode: 'recent' | 'similarity';
  onColorSelect: (c: string) => void;
  onSortChange: (m: 'recent' | 'similarity') => void;
}) {
  const btn = (label: string, active: boolean, onClick: () => void) => (
    <button
      onClick={onClick}
      style={{
        background: active ? 'rgba(99,102,241,0.18)' : 'rgba(255,255,255,0.04)',
        border: `1px solid ${active ? 'rgba(99,102,241,0.5)' : 'rgba(255,255,255,0.08)'}`,
        borderRadius: 6,
        color: active ? '#c7d2fe' : '#64748b',
        fontSize: 11,
        fontFamily: "'SF Mono', ui-monospace, monospace",
        cursor: 'pointer',
        padding: '4px 10px',
        transition: 'all 0.15s',
      }}
    >
      {label}
    </button>
  );

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '10px 28px',
      borderBottom: '1px solid rgba(255,255,255,0.06)',
      flexShrink: 0,
      flexWrap: 'wrap',
    }}>
      {/* Sort section */}
      <span style={{ color: '#374151', fontSize: 10, fontFamily: "'SF Mono', ui-monospace, monospace", letterSpacing: '0.08em', marginRight: 2 }}>SORT</span>
      {btn('Recent', sortMode === 'recent', () => onSortChange('recent'))}
      {btn('Similarity', sortMode === 'similarity', () => onSortChange('similarity'))}

      {uniqueColors.length > 0 && (
        <>
          <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.08)', margin: '0 4px' }} />
          <span style={{ color: '#374151', fontSize: 10, fontFamily: "'SF Mono', ui-monospace, monospace", letterSpacing: '0.08em', marginRight: 2 }}>COLOR</span>
          {uniqueColors.map(color => (
            <button
              key={color}
              onClick={() => onColorSelect(color)}
              title={color}
              style={{
                width: 20,
                height: 20,
                borderRadius: '50%',
                background: color,
                border: `2px solid ${activeColor === color ? '#ffffff' : 'rgba(255,255,255,0.15)'}`,
                cursor: 'pointer',
                padding: 0,
                flexShrink: 0,
                boxShadow: activeColor === color ? `0 0 0 2px rgba(255,255,255,0.4)` : 'none',
                transition: 'border-color 0.15s, box-shadow 0.15s',
              }}
            />
          ))}
          {activeColor && btn('Clear', false, () => onColorSelect(activeColor))}
        </>
      )}
    </div>
  );
}

// ── Grid card ─────────────────────────────────────────────────────────────────

function GridCard({
  item,
  onClick,
  onColorExtracted,
}: {
  item: PortfolioItem;
  onClick: () => void;
  onColorExtracted?: (id: string, color: string) => void;
}) {
  const [svgContent, setSvgContent] = useState<string | null>(null);

  useEffect(() => {
    fetchPortfolioItem(item.artwork_id)
      .then(d => {
        setSvgContent(d.svg_content);
        const color = extractBgColor(d.svg_content);
        if (color) onColorExtracted?.(item.artwork_id, color);
      })
      .catch(() => {});
  }, [item.artwork_id]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <button
      onClick={onClick}
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: 10,
        overflow: 'hidden',
        cursor: 'pointer',
        padding: 0,
        textAlign: 'left',
        transition: 'border-color 0.15s, transform 0.12s',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'rgba(99,102,241,0.5)';
        e.currentTarget.style.transform = 'translateY(-2px)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      {/* Thumbnail — fixed ratio box, full artwork scaled to fit */}
      <div style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '1',
        background: '#000',
      }}>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {svgContent
            ? <div className="grid-thumb" style={{ width: '100%', height: '100%' }} dangerouslySetInnerHTML={{ __html: svgContent }} />
            : <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'rgba(255,255,255,0.05)' }} />}
        </div>
      </div>
    </button>
  );
}

// ── Artwork detail ────────────────────────────────────────────────────────────

const LABEL_STYLE: React.CSSProperties = {
  color: '#71717a',
  fontSize: 10,
  fontFamily: "'SF Mono', ui-monospace, monospace",
  fontWeight: 600,
  letterSpacing: '0.1em',
  textTransform: 'uppercase',
  marginBottom: 10,
};

const GLASS_PILL: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  padding: '4px 10px',
  borderRadius: 999,
  border: '1px solid rgba(255,255,255,0.1)',
  background: 'rgba(255,255,255,0.05)',
  color: '#a1a1aa',
  fontSize: 10,
  fontFamily: "'SF Mono', ui-monospace, monospace",
  fontWeight: 600,
  letterSpacing: '0.08em',
};

function ArtworkDetailView({
  detail,
  onNodeSelect,
}: {
  detail: PortfolioDetail;
  onNodeSelect?: (nodeId: string) => void;
}) {
  const date = detail.created_at
    ? new Date(detail.created_at).toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : '';

  const handleDownload = () => {
    const blob = new Blob([detail.svg_content], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${detail.artwork_id}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{
      position: 'relative',
      background: 'rgba(255,255,255,0.04)',
      backdropFilter: 'blur(32px) saturate(1.8)',
      WebkitBackdropFilter: 'blur(32px) saturate(1.8)',
      border: '1px solid rgba(255,255,255,0.1)',
      boxShadow: '0 32px 80px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.08)',
      borderRadius: 24,
      maxWidth: 860,
      width: '100%',
      maxHeight: '80vh',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Ambient glow */}
      <div style={{
        position: 'absolute',
        top: -80, right: -80,
        width: 280, height: 280,
        borderRadius: '50%',
        background: 'rgba(255,255,255,0.04)',
        filter: 'blur(56px)',
        pointerEvents: 'none',
      }} />

      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '20px 24px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        flexShrink: 0,
        gap: 12,
        position: 'relative',
        zIndex: 1,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
          <div style={{
            width: 40, height: 40,
            borderRadius: 12,
            background: 'rgba(255,255,255,0.08)',
            border: '1px solid rgba(255,255,255,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <Layers size={18} color="rgba(255,255,255,0.7)" />
          </div>
          <div>
            <div style={{
              color: '#fff', fontFamily: 'monospace', fontSize: 13, fontWeight: 700,
              letterSpacing: '0.02em',
            }}>
              {detail.artwork_id}
            </div>
            {date && (
              <div style={{ color: '#71717a', fontSize: 11, fontFamily: "'SF Mono', ui-monospace, monospace", marginTop: 2 }}>
                {date}
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <div style={GLASS_PILL}>
            <span style={{ position: 'relative', display: 'inline-flex', width: 7, height: 7 }}>
              <span style={{
                position: 'absolute', inset: 0,
                borderRadius: '50%', background: 'rgba(74,222,128,0.7)',
                animation: 'ping 1.5s ease-in-out infinite',
              }} />
              <span style={{
                position: 'relative', display: 'inline-flex',
                width: 7, height: 7, borderRadius: '50%', background: '#22c55e',
              }} />
            </span>
            ACTIVE
          </div>
          <button
            onClick={handleDownload}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '6px 14px',
              borderRadius: 999,
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.06)',
              backdropFilter: 'blur(8px)',
              color: '#d4d4d8',
              fontSize: 11, fontFamily: "'SF Mono', ui-monospace, monospace", fontWeight: 600,
              cursor: 'pointer',
              transition: 'background 0.15s, border-color 0.15s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.1)';
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)';
            }}
          >
            <Download size={12} />
            Download SVG
          </button>
        </div>
      </div>

      {/* Body */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', position: 'relative', zIndex: 1 }}>
        {/* SVG preview */}
        <div style={{
          width: 320,
          flexShrink: 0,
          background: 'rgba(0,0,0,0.25)',
          borderRight: '1px solid rgba(255,255,255,0.07)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
        }}>
          <div
            className="artwork-full"
            style={{
              width: '100%',
              borderRadius: 16,
              overflow: 'hidden',
              border: '1px solid rgba(255,255,255,0.08)',
              background: '#000',
            }}
            dangerouslySetInnerHTML={{ __html: detail.svg_content }}
          />
        </div>

        {/* Info column */}
        <div style={{
          flex: 1, overflowY: 'auto', padding: 24,
          display: 'flex', flexDirection: 'column', gap: 24,
        }}>
          {(detail.voter_ids ?? []).length > 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 8,
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Network size={13} color="rgba(255,255,255,0.5)" />
                </div>
                <span style={LABEL_STYLE}>Source nodes</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {detail.voter_ids.map(id => (
                  <button
                    key={id}
                    onClick={() => onNodeSelect?.(id)}
                    style={{
                      ...GLASS_PILL,
                      fontFamily: 'monospace',
                      cursor: onNodeSelect ? 'pointer' : 'default',
                      transition: 'background 0.15s, border-color 0.15s, color 0.15s',
                    }}
                    onMouseEnter={e => {
                      if (!onNodeSelect) return;
                      e.currentTarget.style.background = 'rgba(99,102,241,0.12)';
                      e.currentTarget.style.borderColor = 'rgba(99,102,241,0.35)';
                      e.currentTarget.style.color = '#c7d2fe';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.background = 'rgba(255,255,255,0.05)';
                      e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)';
                      e.currentTarget.style.color = '#a1a1aa';
                    }}
                  >
                    {id}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div style={{ height: 1, background: 'rgba(255,255,255,0.07)', flexShrink: 0 }} />

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 8,
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <FileText size={13} color="rgba(255,255,255,0.5)" />
              </div>
              <span style={LABEL_STYLE}>Justification trace</span>
            </div>
            {detail.trace_text ? (
              <pre style={{
                margin: 0, color: '#d4d4d8', fontSize: 12,
                fontFamily: 'monospace', lineHeight: 1.8,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              }}>
                {detail.trace_text}
              </pre>
            ) : (
              <p style={{
                color: '#52525b', fontSize: 13,
                fontFamily: "'SF Mono', ui-monospace, monospace", fontStyle: 'italic', margin: 0,
              }}>
                No trace recorded for this artwork.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
