import React, { useEffect, useRef, useState } from 'react';

// ── Entry types ───────────────────────────────────────────────────────────────

export interface PassageEntry {
  id: string;
  type: 'passage';
  nodeId: string;
  sourceTitle: string;
  author: string;
  passage: string;
  weight: number;
}

export interface ReasoningEntry {
  id: string;
  type: 'reasoning';
  description: string;
}

export interface SeparatorEntry {
  id: string;
  type: 'separator';
}

export type TerminalEntry = PassageEntry | ReasoningEntry | SeparatorEntry;

interface Props {
  entries: TerminalEntry[];
  isGenerating: boolean;
  onClear: () => void;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  isActive: boolean;
  onPlayStop: () => void;
  graphTheme?: 'dark' | 'light' | 'earth' | 'blue';
}

// ── Word-wrap helper — splits text into lines of at most maxWidth chars ──────

function wrapLines(text: string, maxWidth: number): string[] {
  const words = text.split(' ');
  const lines: string[] = [];
  let current = '';
  for (const word of words) {
    if (current.length === 0) {
      current = word;
    } else if (current.length + 1 + word.length <= maxWidth) {
      current += ' ' + word;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  return lines;
}

// ── Slug helper — converts a display name to a log-style identifier ───────────

function toSlug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9 ]/g, '').replace(/\s+/g, '_').slice(0, 28);
}

// ── Typewriter — reveals one wrapped line at a time ───────────────────────────
// No <br/> after the final visible line so an inline closing character
// (e.g. a closing quote) stays on the same line as the last word.

function TypewriterText({ text }: { text: string }) {
  const lines = wrapLines(text, 160);
  const [visibleCount, setVisibleCount] = useState(0);
  const indexRef = useRef(0);

  useEffect(() => {
    indexRef.current = 0;
    setVisibleCount(0);
    // Reveal one line every 90ms
    const id = setInterval(() => {
      indexRef.current += 1;
      setVisibleCount(indexRef.current);
      if (indexRef.current >= lines.length) clearInterval(id);
    }, 90);
    return () => clearInterval(id);
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {lines.slice(0, visibleCount).map((line, i) => (
        <span key={i}>{line}{i < visibleCount - 1 && <br />}</span>
      ))}
    </>
  );
}

// ── Log-line styles & sub-components ─────────────────────────────────────────

const MONO: React.CSSProperties = {
  fontFamily: "'SF Mono', ui-monospace, monospace",
  fontSize: 12,
  lineHeight: 1.75,
};

const LOG_LINE: React.CSSProperties = {
  ...MONO,
  marginBottom: 4,
};

function LogPrefix({ source, isLight }: { source: string; isLight?: boolean }) {
  return (
    <>
      <span style={{ color: 'rgba(0,255,128,0.9)', fontWeight: 700 }}>INFO</span>
      <span style={{ color: isLight ? 'rgba(0,0,0,0.2)' : 'rgba(255,255,255,0.2)' }}>:     </span>
      <span style={{ color: isLight ? 'rgba(0,0,0,0.45)' : 'rgba(255,255,255,0.4)' }}>{source}</span>
      <span style={{ color: isLight ? 'rgba(0,0,0,0.2)' : 'rgba(255,255,255,0.2)' }}> - </span>
    </>
  );
}

function LogLine({ source, content, suffix, isLight }: { source: string; content: string; suffix: React.ReactNode; isLight?: boolean }) {
  return (
    <div style={LOG_LINE}>
      <LogPrefix source={source} isLight={isLight} />
      <span style={{ color: isLight ? '#000000' : '#ffffff' }}>"{content}"</span>
      {suffix && <span style={{ color: 'rgba(0,255,128,0.75)' }}> {suffix}</span>}
    </div>
  );
}

// ── Snap breakpoints (fractions of viewport height) ──────────────────────────

const SNAP_FRACS = [0.3, 0.6, 1.0];

function snapHeight(px: number): number {
  const vh = window.innerHeight;
  const points = SNAP_FRACS.map(f => Math.round(f * vh));
  return points.reduce((a, b) => (Math.abs(b - px) < Math.abs(a - px) ? b : a));
}

// ── Scanline texture overlay ──────────────────────────────────────────────────

const SCANLINES = `repeating-linear-gradient(
  to bottom,
  transparent 0px,
  transparent 3px,
  rgba(0,0,0,0.045) 3px,
  rgba(0,0,0,0.045) 4px
)`;

const TAB_H = 36; // height of the bottom tab in px

// ── Main component ────────────────────────────────────────────────────────────

export function ConsciousnessTerminal({ entries, isGenerating, onClear, isOpen, onOpenChange, isActive, onPlayStop, graphTheme = 'dark' }: Props) {
  const isLight = graphTheme === 'light';
  const [heightPx, setHeightPx] = useState(() => Math.round(window.innerHeight * 0.3));
  const [isDragging, setIsDragging] = useState(false);
  const isDraggingRef = useRef(false);
  const dragStartYRef = useRef(0);
  const dragStartHRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to newest entry
  useEffect(() => {
    if (isOpen && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries.length, isOpen]);

  // ── Drag handling ─────────────────────────────────────────────────────────

  const onDragStart = (e: React.MouseEvent) => {
    isDraggingRef.current = true;
    setIsDragging(true);
    dragStartYRef.current = e.clientY;
    dragStartHRef.current = heightPx;
    e.preventDefault();
  };

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const delta = dragStartYRef.current - e.clientY; // drag up = increase height
      const vh = window.innerHeight;
      setHeightPx(Math.max(120, Math.min(vh, dragStartHRef.current + delta)));
    };

    const onUp = () => {
      if (!isDraggingRef.current) return;
      isDraggingRef.current = false;
      setIsDragging(false);
      setHeightPx(h => snapHeight(h));
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  // ── Render ────────────────────────────────────────────────────────────────
  // Single container anchored at bottom: 0. Tab is the first child so it is
  // always the topmost visible element. When collapsed, translateY(heightPx)
  // pushes the content below the viewport — only the tab sticks out.

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: heightPx + TAB_H,
        transform: `translateY(${isOpen ? 0 : heightPx}px)`,
        transition: isDragging ? 'none' : 'transform 0.32s cubic-bezier(0.4, 0, 0.2, 1)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 250,
      }}
    >
      {/* Tab — top of the container, always visible when panel is at bottom */}
      <div style={{ flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
        <button
          onClick={() => onOpenChange(!isOpen)}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            height: TAB_H,
            padding: '0 22px',
            background: isOpen
              ? isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.07)'
              : isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.04)',
            backdropFilter: 'blur(24px) saturate(1.5)',
            WebkitBackdropFilter: 'blur(24px) saturate(1.5)',
            borderTop: isOpen
              ? isLight ? '1px solid rgba(0,0,0,0.2)' : '1px solid rgba(255,255,255,0.22)'
              : isLight ? '1px solid rgba(0,0,0,0.1)' : '1px solid rgba(255,255,255,0.09)',
            borderLeft: isOpen
              ? isLight ? '1px solid rgba(0,0,0,0.2)' : '1px solid rgba(255,255,255,0.22)'
              : isLight ? '1px solid rgba(0,0,0,0.1)' : '1px solid rgba(255,255,255,0.09)',
            borderRight: isOpen
              ? isLight ? '1px solid rgba(0,0,0,0.2)' : '1px solid rgba(255,255,255,0.22)'
              : isLight ? '1px solid rgba(0,0,0,0.1)' : '1px solid rgba(255,255,255,0.09)',
            borderBottom: 'none',
            borderRadius: '8px 8px 0 0',
            color: isOpen
              ? isLight ? 'rgba(0,0,0,0.85)' : 'rgba(255,255,255,0.9)'
              : isLight ? 'rgba(0,0,0,0.45)' : 'rgba(255,255,255,0.4)',
            fontSize: 11,
            fontFamily: "'SF Mono', ui-monospace, monospace",
            fontWeight: 600,
            letterSpacing: '0.1em',
            cursor: 'pointer',
            userSelect: 'none',
            transition: 'background 0.15s, border-color 0.15s, color 0.15s',
          }}
        >
          <span style={{ fontSize: 8, lineHeight: 1 }}>{isOpen ? '▼' : '▲'}</span>
          Terminal
          {isGenerating && (
            <span style={{
              width: 5,
              height: 5,
              borderRadius: '50%',
              background: 'rgba(0,255,128,0.8)',
              display: 'inline-block',
              flexShrink: 0,
              animation: 'pulse 1s ease-in-out infinite',
            }} />
          )}
        </button>
      </div>

      {/* Content panel — fills the rest of the container */}
      <div
        style={{
          flex: 1,
          background: 'rgba(255, 255, 255, 0)',
          backdropFilter: 'blur(30px) saturate(1.8)',
          WebkitBackdropFilter: 'blur(30px) saturate(1.8)',
          borderTop: '1px solid rgba(0, 255, 128, 0.1)',
          boxShadow: '0 -12px 60px rgba(0,0,0,0.7)',
          backgroundImage: SCANLINES,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Drag handle */}
        <div
          onMouseDown={onDragStart}
          style={{
            height: 22,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'ns-resize',
            flexShrink: 0,
          }}
        >
          <div style={{
            width: 40,
            height: 3,
            borderRadius: 2,
            background: 'rgba(255,255,255,0.1)',
          }} />
        </div>

        {/* Header bar */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0 20px 10px',
          flexShrink: 0,
          borderBottom: '1px solid rgba(255,255,255,0.05)',
        }}>
          <span style={{
            color: isActive ? 'rgba(0,255,128,0.7)' : 'rgba(255,255,255,0.25)',
            fontSize: 10,
            fontFamily: "'SF Mono', ui-monospace, monospace",
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            display: 'flex',
            alignItems: 'center',
            gap: 7,
          }}>
            {isActive && (
              <span style={{
                width: 5,
                height: 5,
                borderRadius: '50%',
                background: 'rgba(0,255,128,0.85)',
                display: 'inline-block',
                animation: 'pulse 1s ease-in-out infinite',
              }} />
            )}
            {isActive ? 'generating' : '— last generation —'}
          </span>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            {/* Play / Stop */}
            <button
              onClick={onPlayStop}
              title={isActive ? 'Stop' : 'Play'}
              style={{
                background: 'none',
                border: 'none',
                color: 'rgba(255,255,255,0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                padding: 0,
                transition: 'color 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.85)'; }}
              onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.4)'; }}
            >
              {isActive ? (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                  <rect x="0" y="0" width="5" height="14" rx="1" />
                  <rect x="9" y="0" width="5" height="14" rx="1" />
                </svg>
              ) : (
                <svg width="13" height="15" viewBox="0 0 13 15" fill="currentColor">
                  <path d="M0 0.5L13 7.5L0 14.5V0.5Z" />
                </svg>
              )}
            </button>

            {/* Trash / clear */}
            <button
              onClick={onClear}
              title="Clear terminal"
              style={{
                background: 'none',
                border: 'none',
                color: 'rgba(255,255,255,0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                padding: 0,
                transition: 'color 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.85)'; }}
              onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.4)'; }}
            >
              <svg width="14" height="16" viewBox="0 0 14 16" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
                {/* handle */}
                <path d="M1 4h12" />
                {/* lid tab */}
                <path d="M5 4V2.5h4V4" />
                {/* body */}
                <path d="M2 4l1 11h8l1-11" />
                {/* two lines inside */}
                <line x1="5.5" y1="7" x2="5" y2="13" />
                <line x1="8.5" y1="7" x2="9" y2="13" />
              </svg>
            </button>
          </div>
        </div>

        {/* Scrollable stream */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px 24px 24px',
          }}
        >
          {entries.length === 0 && (
            <LogLine
              source="system"
              content="waiting for generation cycle..."
              suffix={null}
              isLight={isLight}
            />
          )}

          {entries.map(entry => {
            if (entry.type === 'passage') {
              const source = `${toSlug(entry.author)}.${toSlug(entry.sourceTitle)}`;
              return (
                <div key={entry.id} style={LOG_LINE}>
                  <LogPrefix source={source} isLight={isLight} />
                  <span style={{ color: isLight ? '#000000' : '#ffffff', fontWeight: 700 }}>"<TypewriterText text={entry.passage} />"</span>
                  <span style={{ color: 'rgba(0,255,128,0.75)' }}> {entry.weight.toFixed(2)}</span>
                </div>
              );
            }

            if (entry.type === 'reasoning') {
              return (
                <div key={entry.id} style={LOG_LINE}>
                  <LogPrefix source="generation_cycle" isLight={isLight} />
                  <span style={{ color: isLight ? '#000000' : '#ffffff' }}>"{entry.description}"</span>
                  <span style={{ color: 'rgba(0,255,128,0.75)' }}> 200 OK</span>
                </div>
              );
            }

            if (entry.type === 'separator') {
              return (
                <div key={entry.id} style={{
                  borderTop: '1px solid rgba(0,255,128,0.08)',
                  margin: '14px 0 10px',
                }} />
              );
            }

            return null;
          })}
        </div>
      </div>
    </div>
  );
}
