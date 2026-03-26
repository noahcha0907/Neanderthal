/**
 * StackedPanels — 3D perspective stack of portfolio artwork panels.
 *
 * Inputs:  items (PortfolioDetail[]), onSelect callback
 * Outputs: interactive 3D panel stack; calls onSelect when a panel is clicked
 *
 * Interactions:
 *   - Hover: CSS `translate` property animates on compositor thread — zero JS.
 *   - Scroll: GSAP power3.out tween drives a single --scroll-z CSS custom property.
 *             All panel transforms resolve natively via calc() — zero JS per panel per frame.
 *   - Click: calls onSelect with the artwork
 *
 * Virtualization: only WINDOW_SIZE panels are mounted at any time. The window slides
 * as the user scrolls so total DOM count stays fixed regardless of artwork count.
 *
 * Thickness is achieved via two real CSS 3D child faces (left + top edge) that fold
 * perpendicular to the front face using preserve-3d. The viewing angle (rotY=-26,
 * rotX=-28) exposes exactly those two faces.
 */

import { useRef, useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { gsap } from 'gsap';
import type { PortfolioDetail } from '../PortfolioPanel';

const HOVER_EASE  = 'translate 380ms cubic-bezier(0.16, 1, 0.3, 1)';
const Z_SPREAD    = 260;
const HOVER_X     = 200;
const THICKNESS   = 8;
const WINDOW_SIZE = 16;   // panels mounted at once — tune up/down for quality vs perf

interface StackedPanelsProps {
  items: PortfolioDetail[];
  onSelect: (item: PortfolioDetail) => void;
}

interface PanelProps {
  item: PortfolioDetail;
  index: number;   // global index in the full items array
  total: number;
  onClick: () => void;
}

function Panel({ item, index, total, onClick }: PanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  const t             = index / Math.max(total - 1, 1);
  const baseZ         = (index - (total - 1)) * Z_SPREAD;
  const w             = 280 + t * 100;
  const h             = 370 + t * 140;
  const panelOpacity  = 0.3 + t * 0.7;
  const borderOpacity = 0.1 + t * 0.18;

  useEffect(() => {
    const el = panelRef.current;
    if (!el) return;

    // Z position: baseZ is fixed per panel; --scroll-z is the GSAP-animated offset on
    // the parent container. Using var() means the browser resolves all 16 panel
    // transforms natively — no JS subscription, no RAF callback per panel.
    el.style.transform = `translateZ(calc(${baseZ}px + var(--scroll-z, 0px)))`;
    el.style.transition = HOVER_EASE;

    const onEnter = () => {
      el.style.willChange = 'translate';
      el.style.translate = `${HOVER_X}px 0`;
    };
    const onLeave = () => { el.style.translate = '0 0'; };
    const onEnd   = () => { el.style.willChange = 'auto'; };

    el.addEventListener('mouseenter', onEnter);
    el.addEventListener('mouseleave', onLeave);
    el.addEventListener('transitionend', onEnd);
    return () => {
      el.removeEventListener('mouseenter', onEnter);
      el.removeEventListener('mouseleave', onLeave);
      el.removeEventListener('transitionend', onEnd);
    };
  }, [baseZ]);

  return (
    <div
      ref={panelRef}
      onClick={onClick}
      style={{
        position: 'absolute',
        cursor: 'pointer',
        width: w, height: h,
        marginLeft: -w / 2,
        marginTop:  -h / 2,
        transformStyle: 'preserve-3d',
      }}
    >
      {/* ── Front face ──────────────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', inset: 0, overflow: 'hidden',
        background: '#000', opacity: panelOpacity,
      }}>
        <div
          style={{ position: 'absolute', inset: 0 }}
          dangerouslySetInnerHTML={{ __html: item.svg_content }}
        />
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'linear-gradient(to bottom, rgba(0,0,0,0.11) 0%, rgba(0,0,0,0.28) 100%)',
        }} />
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          border: `1px solid rgba(255,255,255,${borderOpacity})`,
          boxSizing: 'border-box',
        }} />
      </div>

      {/* ── Left edge ───────────────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: 0, left: 0,
        width: THICKNESS, height: h,
        background: 'rgba(255,255,255,0)',
        opacity: panelOpacity,
        transformOrigin: 'left center',
        transform: 'rotateY(90deg)',
        pointerEvents: 'none',
      }} />

      {/* ── Top edge ────────────────────────────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: 0, left: 0,
        width: w, height: THICKNESS,
        background: 'rgba(34,34,34,0.48)',
        opacity: panelOpacity,
        transformOrigin: 'top center',
        transform: 'rotateX(-90deg)',
        pointerEvents: 'none',
      }} />
    </div>
  );
}

export default function StackedPanels({ items, onSelect }: StackedPanelsProps) {
  const containerRef   = useRef<HTMLDivElement>(null);
  const innerRef       = useRef<HTMLDivElement>(null);
  const accumRef       = useRef(0);
  const tweenRef       = useRef<gsap.core.Tween | null>(null);
  const scrollObj      = useRef({ z: 0 });
  const windowStartRef = useRef(0);
  const total          = items.length;

  // Start with the newest (last) panels visible.
  const [windowStart, setWindowStart] = useState(() => Math.max(0, total - WINDOW_SIZE));

  useEffect(() => {
    const initial = Math.max(0, total - WINDOW_SIZE);
    windowStartRef.current = initial;
    setWindowStart(initial);
  }, [total]);

  useEffect(() => {
    const el    = containerRef.current;
    const inner = innerRef.current;
    if (!el || !inner) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const modeScale = e.deltaMode === 1 ? 20 : e.deltaMode === 2 ? 400 : 1;
      const delta = Math.sign(e.deltaY) * Math.min(Math.abs(e.deltaY * modeScale), 120);
      const max   = Math.max(0, (total - 1) * Z_SPREAD);
      accumRef.current = Math.max(0, Math.min(accumRef.current + delta, max));

      tweenRef.current?.kill();
      tweenRef.current = gsap.to(scrollObj.current, {
        z: accumRef.current,
        duration: 0.75,
        ease: 'power3.out',
        onUpdate() {
          // One property write per frame drives all 16 panel transforms via CSS calc().
          inner.style.setProperty('--scroll-z', `${scrollObj.current.z}px`);

          // Slide the render window so the panel nearest the camera stays centered.
          // centerIdx: which global panel is closest to z=0 (the camera).
          const centerIdx = Math.max(0, Math.min(
            Math.round((total - 1) - scrollObj.current.z / Z_SPREAD),
            total - 1,
          ));
          const idealStart = Math.max(0, Math.min(
            centerIdx - Math.floor(WINDOW_SIZE / 2),
            total - WINDOW_SIZE,
          ));
          // Only trigger a React re-render when the window needs to shift.
          if (Math.abs(idealStart - windowStartRef.current) >= 2) {
            windowStartRef.current = idealStart;
            setWindowStart(idealStart);
          }
        },
      });
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [total]);

  const visibleItems = items.slice(windowStart, windowStart + WINDOW_SIZE);

  return (
    <motion.div
      ref={containerRef}
      initial={{ x: '-30vw', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 55, damping: 20, mass: 1.2 }}
      style={{
        width: '100%', height: '100%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        perspective: '9000px',
        userSelect: 'none',
      }}
    >
      <div
        ref={innerRef}
        style={{
          transform: 'rotateY(-30deg) rotateX(-30deg)',
          transformStyle: 'preserve-3d',
          position: 'relative',
          width: 0, height: 0,
        }}
      >
        {visibleItems.map((item, visibleIdx) => (
          <Panel
            key={item.artwork_id}
            item={item}
            index={windowStart + visibleIdx}
            total={total}
            onClick={() => onSelect(item)}
          />
        ))}
      </div>
    </motion.div>
  );
}
