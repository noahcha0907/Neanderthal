/**
 * GooeyText — morphing text with an SVG gooey blur+threshold filter.
 *
 * Inputs:  texts (string[]), morphTime (s), cooldownTime (s), style overrides
 * Outputs: two overlapping spans that cross-fade with a blur-based morph effect
 *
 * How the gooey effect works:
 *   Each span is blurred proportionally to how far it is from fully visible.
 *   The SVG feColorMatrix then thresholds the alpha channel, snapping semi-
 *   transparent blurred pixels into solid ones — this creates the liquid blob
 *   merging appearance between the two words.
 *
 * Ported from the shadcn gooey-text-morphing component; Tailwind replaced with
 * inline styles. Key fixes over the original:
 *   - Filter div is sized to fill the container (original collapses to 0×0)
 *   - Spans are vertically centered via top/transform (original sticks to top)
 *   - cancelAnimationFrame cleanup (original is a no-op)
 *   - Ease-in applied to morph fraction for slow→snappy feel
 *   - Increased blur coefficient for more pronounced gooey blobs
 */

import * as React from 'react';

interface GooeyTextProps {
  texts: string[];
  morphTime?: number;
  cooldownTime?: number;
  style?: React.CSSProperties;
  textStyle?: React.CSSProperties;
  align?: 'center' | 'left';
}

export function GooeyText({
  texts,
  morphTime = 1,
  cooldownTime = 0.25,
  style,
  textStyle,
  align = 'center',
}: GooeyTextProps) {
  const text1Ref = React.useRef<HTMLSpanElement>(null);
  const text2Ref = React.useRef<HTMLSpanElement>(null);

  React.useEffect(() => {
    let textIndex = texts.length - 1;
    let time = performance.now();
    let morph = 0;
    let cooldown = cooldownTime;
    let rafId: number;

    const setMorph = (fraction: number) => {
      if (!text1Ref.current || !text2Ref.current) return;
      // Linear fraction keeps both words simultaneously visible in the middle,
      // which is the overlap window where the SVG threshold merges them into a
      // single gooey blob. Easing here breaks the effect — it empties the canvas
      // before the next word appears, making it look like two separate fades.
      const f = Math.min(fraction, 1);
      // BLUR=4: at f=0.5 this gives 4px blur on each word — enough to spread
      // letter edges so the SVG threshold merges them into connected blobs,
      // but small enough that both words stay above the alpha threshold and
      // remain visible during the overlap window (f ≈ 0.25–0.75).
      const BLUR = 4;
      text2Ref.current.style.filter  = `blur(${Math.min(BLUR / f - BLUR, 100)}px)`;
      text2Ref.current.style.opacity = `${Math.pow(f, 0.4) * 100}%`;
      const inv = 1 - f;
      text1Ref.current.style.filter  = `blur(${Math.min(BLUR / inv - BLUR, 100)}px)`;
      text1Ref.current.style.opacity = `${Math.pow(inv, 0.4) * 100}%`;
    };

    const doCooldown = () => {
      morph = 0;
      if (!text1Ref.current || !text2Ref.current) return;
      text2Ref.current.style.filter  = '';
      text2Ref.current.style.opacity = '100%';
      text1Ref.current.style.filter  = '';
      text1Ref.current.style.opacity = '0%';
    };

    const doMorph = () => {
      morph -= cooldown;
      cooldown = 0;
      let fraction = morph / morphTime;
      if (fraction > 1) {
        cooldown = cooldownTime;
        fraction = 1;
      }
      setMorph(fraction);
    };

    const tick = (now: number) => {
      const dt = (now - time) / 1000;
      time = now;
      const shouldIncrement = cooldown > 0;
      cooldown -= dt;

      if (cooldown <= 0) {
        if (shouldIncrement) {
          textIndex = (textIndex + 1) % texts.length;
          if (text1Ref.current) text1Ref.current.textContent = texts[textIndex % texts.length];
          if (text2Ref.current) text2Ref.current.textContent = texts[(textIndex + 1) % texts.length];
        }
        doMorph();
      } else {
        doCooldown();
      }

      rafId = requestAnimationFrame(tick);
    };

    if (text1Ref.current) text1Ref.current.textContent = texts[texts.length - 1];
    if (text2Ref.current) text2Ref.current.textContent = texts[0];

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [texts, morphTime, cooldownTime]);

  // Spans must overlay each other exactly — absolute within the filter div
  const spanBase: React.CSSProperties = {
    position: 'absolute',
    top: '55%',   // slightly below center so text sits lower in the container
    display: 'inline-block',
    userSelect: 'none',
    whiteSpace: 'nowrap',
    textAlign: align,
    ...(align === 'left'
      ? { left: 0, transform: 'translateY(-50%)' }
      : { left: '50%', transform: 'translate(-50%, -50%)' }),
    ...textStyle,
  };

  return (
    <div style={{ position: 'relative', overflow: 'visible', ...style }}>
      {/* Zero-size SVG — defines the filter only, no layout contribution */}
      <svg style={{ position: 'absolute', width: 0, height: 0 }} aria-hidden>
        <defs>
          {/*
            x/y/width/height expand the filter processing region well beyond
            the element's bounding box. The default (±10%) is only ±3px on a
            32px container — blurred pixels escaping that region are clipped
            before the threshold step, severing the blob connection mid-morph.
          */}
          <filter
            id="gooey-threshold"
            x="-20%" y="-80%"
            width="140%" height="260%"
          >
            <feColorMatrix
              in="SourceGraphic"
              type="matrix"
              values="1 0 0 0 0
                      0 1 0 0 0
                      0 0 1 0 0
                      0 0 0 255 -140"
            />
          </filter>
        </defs>
      </svg>

      {/*
        Filter div MUST fill the container with real dimensions.
        If it collapses to 0×0 (both children are absolute), the SVG
        filter has nothing to paint on and the effect disappears.
      */}
      <div style={{
        position: 'absolute',
        inset: 0,
        overflow: 'visible',
        filter: 'url(#gooey-threshold)',
      }}>
        <span ref={text1Ref} style={spanBase} />
        <span ref={text2Ref} style={spanBase} />
      </div>
    </div>
  );
}
