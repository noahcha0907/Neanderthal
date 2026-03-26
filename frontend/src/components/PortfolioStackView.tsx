/**
 * PortfolioStackView — full-screen portfolio overlay with 3D stacked panel navigation.
 *
 * Inputs:  onClose callback, optional onNodeSelect for graph navigation
 * Outputs: renders over the app; transitions between stack view and artwork detail
 *
 * Flow:
 *   1. Fetches the 20 most recent portfolio items with full detail on mount
 *   2. Displays them in the StackedPanels 3D view
 *   3. On panel click: transitions to detail view (scales in, shows artwork info)
 *   4. Close/back button returns to stack or exits the overlay entirely
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Download, Layers, Network, FileText } from 'lucide-react';
import StackedPanels from './ui/stacked-panels';
import { fetchPortfolio, fetchPortfolioItem } from '../api/client';
import type { PortfolioDetail } from './PortfolioPanel';

interface PortfolioStackViewProps {
  onClose: () => void;
  onNodeSelect?: (nodeId: string) => void;
}

export function PortfolioStackView({ onClose, onNodeSelect }: PortfolioStackViewProps) {
  const [items, setItems] = useState<PortfolioDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDetail, setSelectedDetail] = useState<PortfolioDetail | null>(null);

  useEffect(() => {
    fetchPortfolio()
      .then(async list => {
        const ordered = [...list].sort((a, b) =>
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
        const details = await Promise.all(
          ordered.map(item => fetchPortfolioItem(item.artwork_id).catch(() => null)),
        );
        setItems(details.filter((d): d is PortfolioDetail => d !== null));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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
        background: 'rgba(255, 255, 255, 0.28)',
        backdropFilter: 'blur(9px)',
        WebkitBackdropFilter: 'blur(9px)',
      }}
    >
      <style>{`@keyframes ping { 75%,100% { transform: scale(2); opacity: 0; } }`}</style>
      {/* Back / Close button */}
      <button
        onClick={inDetail ? () => setSelectedDetail(null) : onClose}
        style={{
          position: 'fixed',
          top: 20,
          right: 20,
          zIndex: 1100,
          background: 'rgba(255,255,255,0.05)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 8,
          color: '#94a3b8',
          fontSize: 12,
          fontFamily: "'SF Mono', ui-monospace, monospace",
          cursor: 'pointer',
          padding: '6px 14px',
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
        {inDetail ? '← Back' : '× Close'}
      </button>

      <AnimatePresence mode="wait">
        {!inDetail ? (
          <motion.div
            key="stack"
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.18 }}
            style={{ width: '100%', height: '100%' }}
          >
            {loading ? (
              <div style={{
                width: '100%', height: '100%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#475569', fontFamily: "'SF Mono', ui-monospace, monospace", fontSize: 13,
              }}>
                Loading…
              </div>
            ) : items.length === 0 ? (
              <div style={{
                width: '100%', height: '100%',
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                gap: 12, opacity: 0.5,
              }}>
                <div style={{ fontSize: 32, color: '#475569' }}>◎</div>
                <div style={{ color: '#475569', fontFamily: "'SF Mono', ui-monospace, monospace", fontSize: 13 }}>
                  No artworks yet
                </div>
              </div>
            ) : (
              <StackedPanels items={items} onSelect={setSelectedDetail} />
            )}
          </motion.div>
        ) : (
          // Panel expands to fill screen and shows detail
          <motion.div
            key="detail"
            initial={{ opacity: 0, scale: 0.82 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.82 }}
            transition={{ type: 'spring', stiffness: 260, damping: 26 }}
            style={{
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 24,
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

// ── Artwork detail (shown after panel click) ──────────────────────────────────

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
      maxHeight: '90vh',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Inner glow — top-right ambient */}
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
          {/* Icon container */}
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

        {/* Status pills */}
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

          {/* Source nodes */}
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

          {/* Divider */}
          <div style={{ height: 1, background: 'rgba(255,255,255,0.07)', flexShrink: 0 }} />

          {/* Justification trace */}
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
