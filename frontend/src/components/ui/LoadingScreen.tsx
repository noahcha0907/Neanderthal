/**
 * LoadingScreen — full-screen splash shown while the graph data is fetching.
 *
 * Inputs:  visible (bool), onDone callback fired after the exit animation completes
 * Outputs: pulsing grid canvas animation + 0→100% counter, fades out on completion
 *
 * Counter animates naturally from 0→99 over ~2.4s. When `visible` flips false
 * (graph loaded), the counter snaps to 100 and the screen fades out.
 *
 * GraphReloadOverlay — lightweight sibling used for graph re-simulations.
 * Shows the cylinder animation over a transparent background; fades out when
 * `visible` flips false. No counter, no progress bar.
 */

import { useRef, useEffect, useState, useCallback } from 'react';

interface LoadingScreenProps {
  visible: boolean;
  onDone: () => void;
}

// ── Cylindrical analysis animation (canvas) ───────────────────────────────────
// Adapted from set-of-animations-4. Scaled to fit the LoadingScreen canvas size.

const easeInOutCubic = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

function startCylindricalAnalysis(ctx: CanvasRenderingContext2D): () => void {
  let animId: number;
  let time = 0;
  let lastTime = 0;

  const W = ctx.canvas.width;
  const H = ctx.canvas.height;
  const cx = W / 2;
  const cy = H / 2;
  // Scale all spatial params proportionally to canvas size (ref was 180px)
  const scale  = W / 180;
  const radius    = 60  * scale;
  const height    = 100 * scale;
  const numLayers = 15;
  const dotsPerLayer = 25;
  const scanWidth = 15 * scale;

  const draw = (timestamp: number) => {
    if (!lastTime) lastTime = timestamp;
    time += (timestamp - lastTime) * 0.001 * 0.5;
    lastTime = timestamp;

    ctx.clearRect(0, 0, W, H);

    const easedTime = easeInOutCubic((Math.sin(time * 5) + 1) / 2);
    const scanY = cy + (easedTime * 2 - 1) * (height / 2);

    for (let i = 0; i < numLayers; i++) {
      const layerY = cy + (i / (numLayers - 1) - 0.5) * height;
      const rot    = time * (0.2 + (i % 2) * 0.1);

      for (let j = 0; j < dotsPerLayer; j++) {
        const angle = (j / dotsPerLayer) * Math.PI * 2 + rot;
        const x     = Math.cos(angle) * radius;
        const z     = Math.sin(angle) * radius;
        const depth = (z + radius) / (radius * 2);
        const pX    = cx + x * depth;
        const pY    = layerY;

        const distToScan  = Math.abs(pY - scanY);
        const scanEffect  = distToScan < scanWidth
          ? Math.cos((distToScan / scanWidth) * (Math.PI / 2))
          : 0;

        const dotSize = Math.max(0, depth * 1.5 * scale + scanEffect * 2 * scale);
        const opacity = Math.max(0, depth * 0.5 + scanEffect * 0.5);

        ctx.beginPath();
        ctx.arc(pX, pY, dotSize, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${opacity})`;
        ctx.fill();
      }
    }

    animId = requestAnimationFrame(draw);
  };

  animId = requestAnimationFrame(draw);
  return () => cancelAnimationFrame(animId);
}

// ── LoadingScreen ──────────────────────────────────────────────────────────────

export function LoadingScreen({ visible, onDone }: LoadingScreenProps) {
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const stopAnim     = useRef<(() => void) | null>(null);
  const [count, setCount]     = useState(0);
  const [fading, setFading]   = useState(false);
  const countRef     = useRef(0);
  const rafCount     = useRef<number | null>(null);
  const loadedRef    = useRef(false);

  // Start canvas animation on mount
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    stopAnim.current = startCylindricalAnalysis(ctx);
    return () => stopAnim.current?.();
  }, []);

  const finishUp = useCallback(() => {
    if (rafCount.current !== null) cancelAnimationFrame(rafCount.current);
    setCount(100);
    countRef.current = 100;
    // Brief pause at 100%, then fade
    setTimeout(() => {
      setFading(true);
      setTimeout(onDone, 500); // matches fade-out duration
    }, 300);
  }, [onDone]);

  // Animate counter 0 → 99 over ~2.4s
  useEffect(() => {
    const duration = 5000; // ms
    const start    = performance.now();

    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      // Ease-out curve so it slows near 99
      const eased = 1 - Math.pow(1 - progress, 2.5);
      const next  = Math.floor(eased * 99);

      if (next !== countRef.current) {
        countRef.current = next;
        setCount(next);
      }

      if (progress < 1) {
        rafCount.current = requestAnimationFrame(tick);
      } else {
        // Counter reached 99 — wait for `visible` to flip false
        rafCount.current = null;
        if (loadedRef.current) finishUp();
      }
    };

    rafCount.current = requestAnimationFrame(tick);
    return () => {
      if (rafCount.current !== null) cancelAnimationFrame(rafCount.current);
    };
  }, [finishUp]);

  // When loading finishes, snap to 100 (or wait if counter hasn't reached 99 yet)
  useEffect(() => {
    if (!visible) {
      loadedRef.current = true;
      // If counter animation already finished, complete immediately
      if (rafCount.current === null) finishUp();
    }
  }, [visible, finishUp]);

  if (!visible && !fading) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 9999,
      background: '#0047FF',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 32,
      opacity: fading ? 0 : 1,
      transition: 'opacity 500ms ease',
      pointerEvents: fading ? 'none' : 'all',
    }}>
      {/* Scanline overlay */}
      <div style={{
        position: 'absolute',
        inset: 0,
        backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,20,0.18) 3px, rgba(0,0,20,0.18) 4px)',
        pointerEvents: 'none',
      }} />

      <canvas
        ref={canvasRef}
        width={135}
        height={135}
        style={{ position: 'relative', zIndex: 1 }}
      />
      {/* Thin progress bar */}
      <div style={{
        position: 'relative',
        zIndex: 1,
        width: 400,
        height: 3,
        background: 'rgba(255,255,255,0.2)',
        borderRadius: 1,
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${count}%`,
          background: 'rgba(255,255,255,0.9)',
          borderRadius: 1,
          transition: 'width 80ms linear',
        }} />
      </div>
    </div>
  );
}

// ── GraphReloadOverlay ─────────────────────────────────────────────────────────
// Simple overlay for graph re-simulations: just the cylinder animation over a
// transparent background. No counter. Fades out when `visible` flips false.
// Always mounted with visible=true (parent controls via key remount).

export function GraphReloadOverlay({ visible }: { visible: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [alive, setAlive] = useState(true);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    return startCylindricalAnalysis(ctx);
  }, []);

  useEffect(() => {
    if (!visible) {
      const t = setTimeout(() => setAlive(false), 500);
      return () => clearTimeout(t);
    }
  }, [visible]);

  if (!alive) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 9998,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      pointerEvents: 'none',
      opacity: visible ? 1 : 0,
      transition: 'opacity 500ms ease',
    }}>
      <canvas ref={canvasRef} width={135} height={135} />
    </div>
  );
}
