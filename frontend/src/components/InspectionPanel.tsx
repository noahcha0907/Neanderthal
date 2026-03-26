import { useEffect, useState } from 'react';
import { fetchPortfolioItem } from '../api/client';
import type { GraphNode } from '../types/graph';
import { nodeColorHex } from '../utils/nodeStyle';

interface Props {
  node: GraphNode | null;
  onClose: () => void;
}

export function InspectionPanel({ node, onClose }: Props) {
  const [portfolio, setPortfolio] = useState<{ svg_content: string; trace_text: string } | null>(null);
  const [portfolioLoading, setPortfolioLoading] = useState(false);

  // Fetch SVG + trace whenever an artwork node is selected
  useEffect(() => {
    if (node?.kind !== 'artwork' || !node.artwork_id) {
      setPortfolio(null);
      return;
    }
    setPortfolioLoading(true);
    fetchPortfolioItem(node.artwork_id)
      .then(item => setPortfolio({ svg_content: item.svg_content, trace_text: item.trace_text }))
      .catch(() => setPortfolio(null))
      .finally(() => setPortfolioLoading(false));
  }, [node?.kind, node?.artwork_id]);

  if (!node) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 20,
      right: node.kind === 'artwork' ? 320 : 20,
      width: node.kind === 'artwork' ? 400 : 320,
      maxHeight: '85vh',
      overflowY: 'auto',
      background: 'rgba(255,255,255,0.04)',
      backdropFilter: 'blur(40px) saturate(1.8)',
      WebkitBackdropFilter: 'blur(40px) saturate(1.8)',
      border: '1px solid rgba(255,255,255,0.1)',
      boxShadow: '0 16px 48px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08)',
      borderRadius: 16,
      padding: 20,
      color: '#e2e8f0',
      fontFamily: "'SF Mono', ui-monospace, monospace",
      fontSize: 13,
      zIndex: 1000,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{
          background: nodeColorHex(node.kind, node.doc_type),
          color: '#0f172a',
          padding: '2px 8px',
          borderRadius: 4,
          fontSize: 11,
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: 1,
        }}>
          {node.kind === 'source' ? (node.doc_type ?? 'source') : node.kind}
        </span>
        <button onClick={onClose} style={{
          background: 'rgba(255,255,255,0.07)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 999,
          color: 'rgba(255,255,255,0.5)',
          cursor: 'pointer',
          fontSize: 16,
          lineHeight: 1,
          width: 26,
          height: 26,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}>×</button>
      </div>

      {node.kind === 'source' && (
        <>
          <h3 style={{ margin: '0 0 4px', fontSize: 15, color: '#f1f5f9' }}>{node.title ?? '—'}</h3>
          {node.author && <p style={{ margin: '0 0 4px', color: '#94a3b8' }}>{node.author}{node.year ? ` · ${node.year}` : ''}</p>}
          {node.chunk_index !== undefined && <p style={{ margin: '0 0 12px', color: '#475569', fontSize: 12 }}>Chunk #{node.chunk_index}</p>}
          {node.text && (
            <p style={{
              margin: 0,
              color: '#cbd5e1',
              lineHeight: 1.6,
              borderTop: '1px solid rgba(255,255,255,0.08)',
              paddingTop: 12,
              fontStyle: 'italic',
            }}>
              "{node.text}"
            </p>
          )}
        </>
      )}

      {node.kind === 'concept' && (
        <h3 style={{ margin: 0, fontSize: 17, textTransform: 'capitalize', color: '#f1f5f9' }}>
          {node.label ?? node.id}
        </h3>
      )}

      {node.kind === 'artwork' && (
        <>
          <h3 style={{ margin: '0 0 4px', fontSize: 15, color: '#f1f5f9' }}>Artwork</h3>
          <p style={{ margin: '0 0 8px', color: '#94a3b8', fontFamily: 'monospace', fontSize: 11 }}>{node.artwork_id}</p>
          {node.created_at && (
            <p style={{ margin: '0 0 16px', color: '#475569', fontSize: 12 }}>
              {new Date(node.created_at).toLocaleString()}
            </p>
          )}

          {portfolioLoading && (
            <p style={{ color: '#475569', fontSize: 12 }}>Loading…</p>
          )}

          {!portfolioLoading && portfolio && (
            <>
              {/* SVG preview */}
              <div
                style={{
                  width: '100%',
                  aspectRatio: '1',
                  background: 'rgba(0,0,0,0.35)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: 10,
                  overflow: 'hidden',
                  marginBottom: 16,
                }}
                dangerouslySetInnerHTML={{ __html: portfolio.svg_content }}
              />

              {/* Justification trace */}
              <div style={{
                color: '#64748b',
                fontSize: 10,
                letterSpacing: 1,
                textTransform: 'uppercase',
                marginBottom: 8,
              }}>
                Justification trace
              </div>
              {portfolio.trace_text ? (
                <pre style={{
                  margin: 0,
                  color: '#94a3b8',
                  fontSize: 11,
                  fontFamily: 'monospace',
                  lineHeight: 1.7,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  borderTop: '1px solid rgba(255,255,255,0.06)',
                  paddingTop: 10,
                }}>
                  {portfolio.trace_text}
                </pre>
              ) : (
                <p style={{ color: '#475569', fontSize: 12, fontStyle: 'italic' }}>
                  No trace recorded for this artwork.
                </p>
              )}
            </>
          )}

          {!portfolioLoading && !portfolio && (
            <p style={{ color: '#f87171', fontSize: 12 }}>SVG file not found on server.</p>
          )}
        </>
      )}
    </div>
  );
}
