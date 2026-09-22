import {useEffect, useRef, useState} from 'react';

/**
 * Measured container width, so labels keep a fixed pixel size instead of being
 * scaled by a viewBox. SSR renders at `fallback`, then the client corrects it.
 */
export function useChartWidth(fallback = 720) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(fallback);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => {
      const next = entry.contentRect.width;
      if (next > 0) setWidth(next);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return {ref, width};
}
