import { useCallback, useEffect, useRef, useState } from 'react';

const BOTTOM_THRESHOLD_PX = 80;

export function useAutoScroll<T>(dependency: T) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [pinnedToBottom, setPinnedToBottom] = useState(true);

  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setPinnedToBottom(distanceFromBottom < BOTTOM_THRESHOLD_PX);
  }, []);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
    setPinnedToBottom(true);
  }, []);

  useEffect(() => {
    if (pinnedToBottom) {
      containerRef.current?.scrollTo({ top: containerRef.current.scrollHeight });
    }
    // dependency drives re-pinning on new content; pinnedToBottom intentionally
    // excluded so a user scroll-up isn't fought by this effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dependency]);

  return { containerRef, pinnedToBottom, handleScroll, scrollToBottom };
}
