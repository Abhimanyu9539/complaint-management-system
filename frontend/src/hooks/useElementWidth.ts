import { useEffect, useRef, useState, type RefObject } from 'react';

/**
 * Measured pixel width of an element, for charts that draw at real coordinates.
 *
 * The alternative — an SVG `viewBox` with `preserveAspectRatio` — is cheaper
 * but wrong here: non-uniform scaling distorts stroke widths (a 1px axis
 * becomes 0.4px on a wide chart and 3px on a narrow one) and makes `<text>`
 * sizes unpredictable. Measuring and redrawing keeps every stroke honest.
 *
 * Returns 0 until the first ResizeObserver frame; callers must not draw at
 * width 0 or the first paint flashes a collapsed chart.
 */
export function useElementWidth(): [RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    // Observe the container, never the SVG itself. An observer callback that
    // resizes its own observed element produces the "ResizeObserver loop
    // completed with undelivered notifications" warning and, on some browsers,
    // a genuine layout loop.
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;

      const next = Math.floor(entry.contentRect.width);
      // Guard before setState: sub-pixel jitter during a CSS transition would
      // otherwise re-render the chart on every animation frame.
      setWidth((current) => (current === next ? current : next));
    });

    observer.observe(element);
    // Seed synchronously so a chart inside an already-laid-out panel does not
    // wait a frame to appear.
    setWidth(Math.floor(element.getBoundingClientRect().width));

    return () => observer.disconnect();
  }, []);

  return [ref, width];
}
