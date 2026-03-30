import { useEffect, useRef, useState } from 'react';
import { gsap } from 'gsap';

export type ActiveTool = 'move' | 'pointer';
export type GraphTheme = 'dark' | 'light' | 'earth' | 'blue';

interface Props {
  activeTool: ActiveTool;
  onToolChange: (tool: ActiveTool) => void;
  isSessionActive: boolean;
  onPlay: () => void;
  onStop: () => void;
  onUpload: (file: File) => Promise<void>;
  onPortfolio: () => void;
  graphTheme: GraphTheme;
  onThemeChange: (theme: GraphTheme) => void;
  nodeCount: number;
  edgeCount: number;
  humanitiesCount: number;
  talentCount: number;
  cursor: { x: number; y: number };
  camera: { azimuth: number; elevation: number };
  orbitLock: boolean;
  onOrbitLockToggle: () => void;
  onResetView: () => void;
}

// ── Upload Modal ───────────────────────────────────────────────────────────────

const ACCEPTED = '.txt,.pdf,.md';

function UploadModal({ onUpload, onClose }: { onUpload: (file: File) => Promise<void>; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const handleSubmit = async () => {
    if (!file) return;
    setStatus('uploading');
    setMessage('');
    try {
      await onUpload(file);
      setStatus('done');
      setMessage(`${file.name} added to session`);
    } catch (e) {
      setStatus('error');
      setMessage(e instanceof Error ? e.message : 'Upload failed');
    }
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
        backdropFilter: 'blur(4px)', zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'rgba(255,255,255,0.05)',
          backdropFilter: 'blur(32px) saturate(1.8)',
          WebkitBackdropFilter: 'blur(32px) saturate(1.8)',
          border: '1px solid rgba(255,255,255,0.12)',
          boxShadow: '0 24px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.08)',
          borderRadius: 20, padding: 28, width: 360,
          display: 'flex', flexDirection: 'column', gap: 16,
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ color: '#e2e8f0', fontSize: 14, fontWeight: 700, fontFamily: "'SF Mono', ui-monospace, monospace" }}>
          Upload document
        </div>
        <div style={{ color: '#64748b', fontSize: 12, fontFamily: "'SF Mono', ui-monospace, monospace", lineHeight: 1.5 }}>
          Add a personal document to influence this session's generations. Accepted formats: .txt, .pdf, .md — up to 5 MB.
        </div>
        <input
          type="file"
          accept={ACCEPTED}
          onChange={e => setFile(e.target.files?.[0] ?? null)}
          style={{
            color: '#94a3b8', fontSize: 12, fontFamily: "'SF Mono', ui-monospace, monospace",
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 6, padding: '6px 10px', cursor: 'pointer',
          }}
        />
        {message && (
          <div style={{ fontSize: 12, fontFamily: "'SF Mono', ui-monospace, monospace", color: status === 'error' ? '#f87171' : '#4ade80' }}>
            {message}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              display: 'inline-flex', alignItems: 'center', padding: '7px 16px',
              borderRadius: 999, border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.55)',
              fontSize: 12, fontFamily: "'SF Mono', ui-monospace, monospace", fontWeight: 600, cursor: 'pointer',
            }}
          >
            {status === 'done' ? 'Close' : 'Cancel'}
          </button>
          {status !== 'done' && (
            <button
              onClick={handleSubmit}
              disabled={status === 'uploading' || !file}
              style={{
                display: 'inline-flex', alignItems: 'center', padding: '7px 16px',
                borderRadius: 999, border: '1px solid rgba(255,255,255,0.22)',
                background: 'rgba(255,255,255,0.12)', color: '#fff',
                fontSize: 12, fontFamily: "'SF Mono', ui-monospace, monospace", fontWeight: 600,
                cursor: status === 'uploading' || !file ? 'default' : 'pointer',
                opacity: status === 'uploading' || !file ? 0.5 : 1,
              }}
            >
              {status === 'uploading' ? 'Uploading…' : 'Upload'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const PANEL_W = 200;

// ── Icons ─────────────────────────────────────────────────────────────────────

function MoveIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 1v14M1 8h14M8 1l-2 3M8 1l2 3M8 15l-2-3M8 15l2-3M1 8l3-2M1 8l3 2M15 8l-3-2M15 8l-3 2" />
    </svg>
  );
}

function PointerIcon() {
  return (
    <svg width="14" height="16" viewBox="0 0 14 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 1l4.5 12 2.5-4 4 2.5L1 1z" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg width="11" height="13" viewBox="0 0 11 13" fill="currentColor">
      <path d="M0 0.5L11 6.5L0 12.5V0.5Z" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
      <rect width="12" height="12" rx="1.5" />
    </svg>
  );
}

// ── Tool button ───────────────────────────────────────────────────────────────

function ToolBtn({
  active,
  onClick,
  icon,
  label,
  isLight,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  isLight?: boolean;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title={label}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        width: '100%',
        padding: '9px 16px',
        background: active
          ? isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.07)'
          : hovered
          ? isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.05)'
          : 'transparent',
        border: 'none',
        borderLeft: active
          ? `2px solid ${isLight ? 'rgba(0,0,0,0.4)' : 'rgba(255,255,255,0.5)'}`
          : '2px solid transparent',
        color: active
          ? isLight ? 'rgba(0,0,0,0.85)' : 'rgba(255,255,255,0.9)'
          : isLight ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.55)',
        fontSize: 12,
        fontFamily: "'SF Mono', ui-monospace, monospace",
        fontWeight: active ? 600 : 400,
        letterSpacing: '0.04em',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'background 0.12s, color 0.12s, border-color 0.12s',
      }}
    >
      {icon}
      {label}
    </button>
  );
}

// ── Isometric cube theme button ────────────────────────────────────────────────

const CUBE_COLORS: Record<GraphTheme, { face: string; border: string; symbol: string }> = {
  light: { face: '#e0e0e0', border: 'rgba(0,0,0,0.2)',        symbol: 'rgba(30,30,30,0.75)'  },
  dark:  { face: '#1a1a1a', border: 'rgba(255,255,255,0.22)', symbol: 'rgba(255,255,255,0.6)' },
  earth: { face: '#3a2410', border: 'rgba(200,140,50,0.4)',   symbol: 'rgba(210,155,70,0.85)' },
  blue:  { face: '#002ea0', border: 'rgba(90,160,255,0.55)',  symbol: 'rgba(130,190,255,0.9)' },
};

const CUBE_THEMES: { id: GraphTheme; title: string }[] = [
  { id: 'light', title: 'Light'          },
  { id: 'dark',  title: 'Dark (default)' },
  { id: 'earth', title: 'Earth'          },
  { id: 'blue',  title: 'Blueprint'      },
];

const CUBE_SIZE = 20;
const CUBE_HALF = CUBE_SIZE / 2;

function IsoCubeThemeBtn({
  theme,
  isActive,
  title,
  onClick,
}: {
  theme: GraphTheme;
  isActive: boolean;
  title: string;
  onClick: () => void;
}) {
  const cubeRef    = useRef<HTMLDivElement>(null);
  const prevActive = useRef(isActive);
  const { face, border, symbol } = CUBE_COLORS[theme];

  // Set initial isometric rotation on mount
  useEffect(() => {
    if (!cubeRef.current) return;
    gsap.set(cubeRef.current, {
      rotateX: 35.264,
      rotateY: isActive ? 225 : 45,
      rotateZ: 0,
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Animate whenever active state changes
  useEffect(() => {
    if (!cubeRef.current) return;
    if (isActive && !prevActive.current) {
      gsap.to(cubeRef.current, { rotateY: 225, duration: 0.8, ease: 'power2.inOut' });
    } else if (!isActive && prevActive.current) {
      gsap.to(cubeRef.current, { rotateY: 45,  duration: 0.8, ease: 'power2.inOut' });
    }
    prevActive.current = isActive;
  }, [isActive]);

  const faceBase: React.CSSProperties = {
    position: 'absolute',
    width:  CUBE_SIZE,
    height: CUBE_SIZE,
    border: `1px solid ${border}`,
    background: face,
    boxShadow: '0 0 8px rgba(0,0,0,0.5) inset',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        flex: 1,
        padding: '8px 0',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {/* perspective wrapper — keeps the 3D cube centred in the button */}
      <div style={{
        width: CUBE_SIZE + 16,
        height: CUBE_SIZE + 16,
        perspective: '1200px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <div
          ref={cubeRef}
          style={{
            position: 'relative',
            width:  CUBE_SIZE,
            height: CUBE_SIZE,
            transformStyle: 'preserve-3d',
          }}
        >
          {/* front — shows + (closed) */}
          <div style={{ ...faceBase, transform: `translateZ(${CUBE_HALF}px)` }}>
            <div style={{ position: 'relative', width: 7, height: 7 }}>
              <div style={{ position: 'absolute', inset: 0, margin: 'auto', width: '100%', height: 1.5, background: symbol }} />
              <div style={{ position: 'absolute', inset: 0, margin: 'auto', width: 1.5, height: '100%', background: symbol }} />
            </div>
          </div>
          {/* back — shows × (open) */}
          <div style={{ ...faceBase, transform: `rotateY(180deg) translateZ(${CUBE_HALF}px)` }}>
            <div style={{ position: 'relative', width: 7, height: 7 }}>
              <div style={{ position: 'absolute', inset: 0, margin: 'auto', width: '100%', height: 1.5, background: symbol, transform: 'rotate(45deg)' }} />
              <div style={{ position: 'absolute', inset: 0, margin: 'auto', width: '100%', height: 1.5, background: symbol, transform: 'rotate(-45deg)' }} />
            </div>
          </div>
          {/* right */}
          <div style={{ ...faceBase, transform: `rotateY(90deg) translateZ(${CUBE_HALF}px)` }} />
          {/* left */}
          <div style={{ ...faceBase, transform: `rotateY(-90deg) translateZ(${CUBE_HALF}px)` }} />
          {/* top */}
          <div style={{ ...faceBase, transform: `rotateX(90deg) translateZ(${CUBE_HALF}px)` }} />
          {/* bottom */}
          <div style={{ ...faceBase, transform: `rotateX(-90deg) translateZ(${CUBE_HALF}px)` }} />
        </div>
      </div>
    </button>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ToolMenu({ activeTool, onToolChange, isSessionActive, onPlay, onStop, onUpload, onPortfolio, graphTheme, onThemeChange, nodeCount, edgeCount, humanitiesCount, talentCount, cursor, camera, orbitLock, onOrbitLockToggle, onResetView }: Props) {
  const isLight = graphTheme === 'light';
  const [isOpen, setIsOpen] = useState(false);
  const [playHovered, setPlayHovered] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadHovered, setUploadHovered] = useState(false);
  const [portfolioHovered, setPortfolioHovered] = useState(false);

  return (
    <>
      {/* Slide-in panel */}
      <div
        style={{
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          width: PANEL_W,
          transform: `translateX(${isOpen ? 0 : -PANEL_W}px)`,
          transition: 'transform 0.28s cubic-bezier(0.4, 0, 0.2, 1)',
          background: isLight ? 'rgba(255,255,255,0.7)' : 'rgba(255, 255, 255, 0.045)',
          backdropFilter: 'blur(40px) saturate(1.8)',
          WebkitBackdropFilter: 'blur(40px) saturate(1.8)',
          borderRight: isLight ? '1px solid rgba(0,0,0,0.1)' : '1px solid rgba(255,255,255,0.07)',
          boxShadow: '4px 0 32px rgba(0,0,0,0.5)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 200,
        }}
      >
        {/* Header */}
        <div style={{
          padding: '24px 16px 12px',
          borderBottom: isLight ? '1px solid rgba(0,0,0,0.07)' : '1px solid rgba(255,255,255,0.05)',
          flexShrink: 0,
        }}>
          <span style={{
            color: isLight ? 'rgba(0,0,0,0.35)' : 'rgba(255,255,255,0.22)',
            fontSize: 9,
            fontFamily: "'SF Mono', ui-monospace, monospace",
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
          }}>
            Tools
          </span>
        </div>

        {/* Tool buttons */}
        <div style={{ paddingTop: 8, flexShrink: 0 }}>
          <ToolBtn
            active={activeTool === 'move'}
            onClick={() => onToolChange('move')}
            icon={<MoveIcon />}
            label="Move (m)"
            isLight={isLight}
          />
          <ToolBtn
            active={activeTool === 'pointer'}
            onClick={() => onToolChange('pointer')}
            icon={<PointerIcon />}
            label="Select (v)"
            isLight={isLight}
          />
        </div>

        {/* ── Camera controls ────────────────────────────────────────── */}
        <div style={{
          display: 'flex',
          gap: 6,
          padding: '6px 16px 8px',
          borderBottom: isLight ? '1px solid rgba(0,0,0,0.07)' : '1px solid rgba(255,255,255,0.05)',
          flexShrink: 0,
        }}>
          {/* Orbit lock toggle */}
          <button
            onClick={onOrbitLockToggle}
            title={orbitLock ? 'Unlock orbit' : 'Auto-orbit'}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              padding: '7px 0',
              background: orbitLock
                ? isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.1)'
                : 'transparent',
              border: orbitLock
                ? isLight ? '1px solid rgba(0,0,0,0.25)' : '1px solid rgba(255,255,255,0.3)'
                : isLight ? '1px solid rgba(0,0,0,0.1)' : '1px solid rgba(255,255,255,0.08)',
              borderRadius: 5,
              color: orbitLock
                ? isLight ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)'
                : isLight ? 'rgba(0,0,0,0.4)' : 'rgba(255,255,255,0.4)',
              fontSize: 10,
              fontFamily: "'SF Mono', ui-monospace, monospace",
              fontWeight: 600,
              letterSpacing: '0.06em',
              cursor: 'pointer',
              transition: 'background 0.12s, border-color 0.12s, color 0.12s',
            }}
          >
            {/* Orbit icon — circular arrow */}
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
              <path d="M9.5 5.5a4 4 0 1 1-1.17-2.83" />
              <polyline points="8.5,1.5 8.5,3.5 6.5,3.5" fill="currentColor" stroke="none" />
              <path d="M8.5 1.5 L8.5 3.5 L6.5 3.5" strokeLinejoin="round" />
            </svg>
            Orbit
          </button>
          {/* Reset view */}
          <button
            onClick={onResetView}
            title="Reset camera"
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              padding: '7px 0',
              background: 'transparent',
              border: isLight ? '1px solid rgba(0,0,0,0.1)' : '1px solid rgba(255,255,255,0.08)',
              borderRadius: 5,
              color: isLight ? 'rgba(0,0,0,0.4)' : 'rgba(255,255,255,0.4)',
              fontSize: 10,
              fontFamily: "'SF Mono', ui-monospace, monospace",
              fontWeight: 600,
              letterSpacing: '0.06em',
              cursor: 'pointer',
              transition: 'background 0.12s, color 0.12s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.07)';
              e.currentTarget.style.color = isLight ? 'rgba(0,0,0,0.75)' : 'rgba(255,255,255,0.8)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = isLight ? 'rgba(0,0,0,0.4)' : 'rgba(255,255,255,0.4)';
            }}
          >
            {/* Target/crosshair icon */}
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
              <circle cx="5.5" cy="5.5" r="3" />
              <line x1="5.5" y1="1" x2="5.5" y2="2.5" />
              <line x1="5.5" y1="8.5" x2="5.5" y2="10" />
              <line x1="1" y1="5.5" x2="2.5" y2="5.5" />
              <line x1="8.5" y1="5.5" x2="10" y2="5.5" />
            </svg>
            Reset
          </button>
        </div>

        {/* ── Info sections ──────────────────────────────────────────── */}
        {(() => {
          const SEC_HEADER: React.CSSProperties = {
            color: isLight ? 'rgba(0,0,0,0.35)' : 'rgba(255,255,255,0.22)',
            fontSize: 9,
            fontFamily: "'SF Mono', ui-monospace, monospace",
            letterSpacing: '0.14em',
            textTransform: 'uppercase' as const,
            marginBottom: 6,
          };
          const ROW: React.CSSProperties = {
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            marginBottom: 3,
          };
          const LBL: React.CSSProperties = {
            color: isLight ? 'rgba(0,0,0,0.35)' : 'rgba(255,255,255,0.22)',
            fontSize: 9,
            fontFamily: "'SF Mono', ui-monospace, monospace",
            letterSpacing: '0.1em',
            textTransform: 'uppercase' as const,
          };
          const VAL: React.CSSProperties = {
            color: isLight ? 'rgba(0,0,0,0.65)' : 'rgba(255,255,255,0.55)',
            fontSize: 11,
            fontFamily: "'SF Mono', ui-monospace, monospace",
          };
          const DIV: React.CSSProperties = {
            borderTop: isLight ? '1px solid rgba(0,0,0,0.07)' : '1px solid rgba(255,255,255,0.05)',
            margin: '10px 0',
          };
          return (
            <div style={{ padding: '12px 16px 0', flexShrink: 0 }}>
              {/* Corpus */}
              <div style={SEC_HEADER}>Corpus</div>
              <div style={ROW}><span style={LBL}>Nodes</span><span style={VAL}>{nodeCount}</span></div>
              <div style={ROW}><span style={LBL}>Edges</span><span style={VAL}>{edgeCount}</span></div>
              <div style={ROW}><span style={LBL}>Humanities</span><span style={VAL}>{humanitiesCount}</span></div>
              <div style={ROW}><span style={LBL}>Talent</span><span style={VAL}>{talentCount}</span></div>

              <div style={DIV} />

              {/* Position */}
              <div style={SEC_HEADER}>Position</div>
              <div style={ROW}>
                <span style={LBL}>Cursor</span>
                <span style={VAL}>{cursor.x} {cursor.y}</span>
              </div>
              <div style={ROW}>
                <span style={LBL}>Azimuth</span>
                <span style={VAL}>{camera.azimuth}°</span>
              </div>
              <div style={ROW}>
                <span style={LBL}>Elevation</span>
                <span style={VAL}>{camera.elevation}°</span>
              </div>

              <div style={DIV} />

              {/* Controls */}
              <div style={SEC_HEADER}>Controls</div>
              {([
                ['M',       'move'],
                ['V',       'select'],
                ['Drag',    'orbit'],
                ['R-drag',  'pan'],
                ['Scroll',  'zoom'],
              ] as const).map(([k, v]) => (
                <div key={k} style={ROW}>
                  <span style={LBL}>{k}</span>
                  <span style={{ ...VAL, color: isLight ? 'rgba(0,0,0,0.35)' : 'rgba(255,255,255,0.3)', fontSize: 10 }}>{v}</span>
                </div>
              ))}
            </div>
          );
        })()}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Theme picker */}
        <div style={{
          padding: '12px 14px',
          borderTop: isLight ? '1px solid rgba(0,0,0,0.07)' : '1px solid rgba(255,255,255,0.05)',
          flexShrink: 0,
        }}>
          <div style={{
            color: isLight ? 'rgba(0,0,0,0.35)' : 'rgba(255,255,255,0.22)',
            fontSize: 9,
            fontFamily: "'SF Mono', ui-monospace, monospace",
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            marginBottom: 8,
          }}>
            Theme
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {CUBE_THEMES.map(t => (
              <IsoCubeThemeBtn
                key={t.id}
                theme={t.id}
                title={t.title}
                isActive={graphTheme === t.id}
                onClick={() => onThemeChange(t.id)}
              />
            ))}
          </div>
        </div>

        {/* Play / Stop + param selector at bottom */}
        <div style={{
          padding: '16px 14px 28px',
          borderTop: isLight ? '1px solid rgba(0,0,0,0.07)' : '1px solid rgba(255,255,255,0.05)',
          flexShrink: 0,
        }}>
          <button
            onClick={isSessionActive ? onStop : onPlay}
            onMouseEnter={() => setPlayHovered(true)}
            onMouseLeave={() => setPlayHovered(false)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 9,
              width: '100%',
              padding: '10px 0',
              background: isSessionActive
                ? playHovered ? 'rgba(239,68,68,0.18)' : 'rgba(239,68,68,0.10)'
                : playHovered
                  ? isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.12)'
                  : isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.06)',
              border: isSessionActive
                ? '1px solid rgba(239,68,68,0.35)'
                : isLight ? '1px solid rgba(0,0,0,0.2)' : '1px solid rgba(255,255,255,0.25)',
              borderRadius: 6,
              color: isSessionActive ? 'rgba(252,165,165,0.9)' : isLight ? 'rgba(0,0,0,0.75)' : 'rgba(255,255,255,0.85)',
              fontSize: 12,
              fontFamily: "'SF Mono', ui-monospace, monospace",
              fontWeight: 600,
              letterSpacing: '0.06em',
              cursor: 'pointer',
              transition: 'background 0.12s, border-color 0.12s',
            }}
          >
            {isSessionActive ? <StopIcon /> : <PlayIcon />}
            {isSessionActive ? 'Stop' : 'Play'}
          </button>

          {/* Upload button — always visible */}
          <button
            onClick={() => setUploadOpen(true)}
            onMouseEnter={() => setUploadHovered(true)}
            onMouseLeave={() => setUploadHovered(false)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 7,
              width: '100%',
              padding: '8px 0',
              marginTop: 8,
              background: uploadHovered
                ? isLight ? 'rgba(0,0,0,0.07)' : 'rgba(255,255,255,0.09)'
                : isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.04)',
              border: isLight ? '1px solid rgba(0,0,0,0.12)' : '1px solid rgba(255,255,255,0.12)',
              borderRadius: 6,
              color: isLight ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.55)',
              fontSize: 11,
              fontFamily: "'SF Mono', ui-monospace, monospace",
              fontWeight: 600,
              letterSpacing: '0.06em',
              cursor: 'pointer',
              transition: 'background 0.12s, border-color 0.12s',
            }}
          >
            ↑ Upload
          </button>

          {/* Portfolio button */}
          <button
            onClick={onPortfolio}
            onMouseEnter={() => setPortfolioHovered(true)}
            onMouseLeave={() => setPortfolioHovered(false)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 7,
              width: '100%',
              padding: '8px 0',
              marginTop: 6,
              background: portfolioHovered
                ? isLight ? 'rgba(0,0,0,0.07)' : 'rgba(255,255,255,0.09)'
                : isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.04)',
              border: isLight ? '1px solid rgba(0,0,0,0.12)' : '1px solid rgba(255,255,255,0.12)',
              borderRadius: 6,
              color: isLight ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.55)',
              fontSize: 11,
              fontFamily: "'SF Mono', ui-monospace, monospace",
              fontWeight: 600,
              letterSpacing: '0.06em',
              cursor: 'pointer',
              transition: 'background 0.12s, border-color 0.12s',
            }}
          >
            Portfolio
          </button>
        </div>

        {/* Tab — child of panel so it rides the same transform, no sync issues */}
        <div
          onClick={() => setIsOpen(o => !o)}
          style={{
            position: 'absolute',
            right: -14,
            top: '50%',
            transform: 'translateY(-50%)',
            width: 14,
            height: 500,
            background: isLight ? 'rgba(255,255,255,0.75)' : 'rgba(255,255,255,0.055)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: isLight ? '1px solid rgba(0,0,0,0.1)' : '1px solid rgba(255,255,255,0.1)',
            borderLeft: 'none',
            borderRadius: '0 7px 7px 0',
            cursor: 'pointer',
            zIndex: 201,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '2px 0 12px rgba(0,0,0,0.35)',
          }}
        >
          <svg
            width="6"
            height="10"
            viewBox="0 0 6 10"
            fill="none"
            stroke={isLight ? 'rgba(0,0,0,0.4)' : 'rgba(255,255,255,0.4)'}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.28s' }}
          >
            <path d="M1 1l4 4-4 4" />
          </svg>
        </div>
      </div>

      {uploadOpen && (
        <UploadModal
          onUpload={onUpload}
          onClose={() => setUploadOpen(false)}
        />
      )}
    </>
  );
}
