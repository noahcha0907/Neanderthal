/**
 * Floating panel — glassmorphism popover with framer-motion spring animation.
 *
 * Adapted from the shadcn floating-panel component. Tailwind replaced with
 * inline styles matching the project's dark glass aesthetic. The trigger
 * renders using the existing .glass-button CSS classes from index.css.
 *
 * Inputs:  FloatingPanelRoot wraps trigger + content and provides shared state.
 * Outputs: Animated popover anchored below the trigger, backdrop blur scrim.
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react';
import { AnimatePresence, MotionConfig, motion } from 'framer-motion';
import { cn } from '../../lib/utils';

const TRANSITION = {
  type: 'spring',
  bounce: 0.1,
  duration: 0.4,
};

// ── Context ──────────────────────────────────────────────────────────────────

interface FloatingPanelContextType {
  isOpen: boolean;
  openFloatingPanel: (rect: DOMRect) => void;
  closeFloatingPanel: () => void;
  uniqueId: string;
  triggerRect: DOMRect | null;
}

const FloatingPanelContext = createContext<FloatingPanelContextType | undefined>(undefined);

function useFloatingPanel() {
  const context = useContext(FloatingPanelContext);
  if (!context) throw new Error('useFloatingPanel must be used within FloatingPanelRoot');
  return context;
}

function useFloatingPanelLogic() {
  const uniqueId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const [triggerRect, setTriggerRect] = useState<DOMRect | null>(null);

  const openFloatingPanel = (rect: DOMRect) => {
    setTriggerRect(rect);
    setIsOpen(true);
  };
  const closeFloatingPanel = () => setIsOpen(false);

  return { isOpen, openFloatingPanel, closeFloatingPanel, uniqueId, triggerRect };
}

// ── Root ─────────────────────────────────────────────────────────────────────

interface FloatingPanelRootProps {
  children: React.ReactNode;
  className?: string;
}

export function FloatingPanelRoot({ children, className }: FloatingPanelRootProps) {
  const logic = useFloatingPanelLogic();
  return (
    <FloatingPanelContext.Provider value={logic}>
      <MotionConfig transition={TRANSITION}>
        <div className={cn('relative', className)}>{children}</div>
      </MotionConfig>
    </FloatingPanelContext.Provider>
  );
}

// ── Trigger ───────────────────────────────────────────────────────────────────
// Renders using the project's existing .glass-button CSS classes.

interface FloatingPanelTriggerProps {
  children: React.ReactNode;
  className?: string;
}

export function FloatingPanelTrigger({ children, className }: FloatingPanelTriggerProps) {
  const { openFloatingPanel, closeFloatingPanel, isOpen } = useFloatingPanel();
  const triggerRef = useRef<HTMLDivElement>(null);

  const handleClick = () => {
    if (isOpen) {
      closeFloatingPanel();
      return;
    }
    if (triggerRef.current) {
      openFloatingPanel(triggerRef.current.getBoundingClientRect());
    }
  };

  return (
    <div ref={triggerRef} className="glass-button-wrap" onClick={handleClick}>
      <button
        className={cn('glass-button', isOpen && 'glass-button--selected', className)}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
      >
        <span className="glass-button-text" style={{ padding: '6px 14px', fontSize: 13, gap: 6 }}>
          {children}
        </span>
      </button>
      <div className="glass-button-shadow" />
    </div>
  );
}

// ── Content ───────────────────────────────────────────────────────────────────

interface FloatingPanelContentProps {
  children: React.ReactNode;
  className?: string;
  /** Width of the popover in px. Defaults to 360. */
  width?: number;
}

export function FloatingPanelContent({ children, className, width = 360 }: FloatingPanelContentProps) {
  const { isOpen, closeFloatingPanel, uniqueId, triggerRect } = useFloatingPanel();
  const contentRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (contentRef.current && !contentRef.current.contains(e.target as Node)) {
        closeFloatingPanel();
      }
    };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [closeFloatingPanel]);

  // Close on Escape
  useEffect(() => {
    const handle = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeFloatingPanel();
    };
    document.addEventListener('keydown', handle);
    return () => document.removeEventListener('keydown', handle);
  }, [closeFloatingPanel]);

  // Right-align to trigger: panel right edge = trigger right edge
  const rightOffset = triggerRect
    ? window.innerWidth - triggerRect.right
    : undefined;
  const topOffset = triggerRect ? triggerRect.bottom + 10 : undefined;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop scrim with blur */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 498,
              background: 'rgba(0, 0, 0, 0.35)',
              backdropFilter: 'blur(4px)',
              WebkitBackdropFilter: 'blur(4px)',
            }}
          />

          {/* Panel */}
          <motion.div
            ref={contentRef}
            id={`floating-panel-${uniqueId}`}
            className={className}
            style={{
              position: 'fixed',
              zIndex: 500,
              width,
              right: rightOffset,
              top: topOffset,
              transformOrigin: 'top right',
              borderRadius: 16,
              background: 'rgba(8, 8, 18, 0.88)',
              backdropFilter: 'blur(28px) saturate(1.8)',
              WebkitBackdropFilter: 'blur(28px) saturate(1.8)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              boxShadow:
                '0 24px 80px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,255,255,0.07)',
              overflow: 'hidden',
            }}
            initial={{ opacity: 0, scale: 0.92, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: -8 }}
            role="dialog"
            aria-modal="true"
          >
            {children}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ── Header ────────────────────────────────────────────────────────────────────

interface FloatingPanelHeaderProps {
  children: React.ReactNode;
}

export function FloatingPanelHeader({ children }: FloatingPanelHeaderProps) {
  return (
    <motion.div
      style={{
        padding: '14px 16px 10px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
        flexShrink: 0,
      }}
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 }}
    >
      {children}
    </motion.div>
  );
}

// ── Body ──────────────────────────────────────────────────────────────────────

interface FloatingPanelBodyProps {
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export function FloatingPanelBody({ children, style }: FloatingPanelBodyProps) {
  return (
    <motion.div
      style={{ flex: 1, overflow: 'hidden', ...style }}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.08 }}
    >
      {children}
    </motion.div>
  );
}

// ── Close hook export ─────────────────────────────────────────────────────────

export { useFloatingPanel };
