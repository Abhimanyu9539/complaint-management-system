import { useEffect, useRef, type RefObject } from 'react';

/**
 * Keyboard behaviour for a slide-over panel, as `Drawer` does it: Escape closes
 * it, focus moves into the panel on open and back to the trigger on close.
 *
 * `onClose` is read through a ref, so callers can pass an inline arrow without
 * the effect re-running (and re-grabbing focus) on every render.
 */
export function useOverlayFocus(
  open: boolean,
  onClose: () => void,
  panelRef: RefObject<HTMLElement | null>,
) {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;

    const returnTo = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCloseRef.current();
    };
    document.addEventListener('keydown', onKeyDown);

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      // Best effort: the trigger can be gone by now.
      returnTo?.focus?.();
    };
  }, [open, panelRef]);
}
