import { useCallback, useEffect, useRef, useState } from 'react';

const BOTTOM_THRESHOLD_PX = 80;
// Same as the list's top padding (py-6), so a message scrolled to the top isn't flush with the edge.
const TOP_GAP_PX = 24;

// Claude-style scrolling: a message the agent just sent scrolls to the top of the view and the
// answer streams in below it without moving the view. Opening a conversation lands at its end.
export function useAutoScroll(lastTurnId: string | undefined, isNewSend: boolean, contentKey: string) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const lastTurnRef = useRef<HTMLDivElement | null>(null);
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

  // Runs only when the last turn changes: a new message was sent, or another conversation opened.
  // Streaming tokens and the turn being saved keep the same last turn, so they never move the view.
  useEffect(() => {
    const container = containerRef.current;
    const lastTurn = lastTurnRef.current;
    if (!container) return;
    if (isNewSend && lastTurn) {
      container.scrollTo({ top: lastTurn.offsetTop - TOP_GAP_PX, behavior: 'smooth' });
    } else {
      container.scrollTo({ top: container.scrollHeight });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastTurnId]);

  // The answer grows without scrolling, so re-check whether "Jump to latest" should show.
  useEffect(() => {
    handleScroll();
  }, [contentKey, handleScroll]);

  return { containerRef, lastTurnRef, pinnedToBottom, handleScroll, scrollToBottom };
}
