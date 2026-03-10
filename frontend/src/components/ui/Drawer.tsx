import { X } from 'lucide-react';
import { useEffect, useRef, type ReactNode } from 'react';
import { ICON_SIZE, IconButton } from './IconButton';

interface DrawerProps {
  open: boolean;
  onClose(): void;
  title: string;
  /** Header rail content, right of the title. */
  actions?: ReactNode;
  /** Sticky footer. Omit for read-only drawers. */
  footer?: ReactNode;
  children: ReactNode;
}

/**
 * Right-anchored slide-in detail panel.
 *
 * Reuses the scrim pattern from `AppShell` verbatim so the two overlays in the
 * app behave identically. Focus moves to the close button on open and returns
 * to whatever opened it on close — without that, keyboard users are dropped at
 * the top of the document every time they dismiss a row detail.
 */
export function Drawer({ open, onClose, title, actions, footer, children }: DrawerProps) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;

    returnFocusRef.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      // The trigger can be gone by now (a row removed by a refresh), so this is
      // a best-effort restore rather than an assertion.
      returnFocusRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40">
      <button
        type="button"
        aria-label="Close details"
        onClick={onClose}
        className="absolute inset-0 bg-black/40 backdrop-blur-[1px]"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="absolute inset-y-0 right-0 flex w-[88%] max-w-[440px] flex-col border-l border-border bg-surface shadow-xl"
        style={{ animation: 'slide-in-right 0.2s ease-out' }}
      >
        <header className="flex h-13 shrink-0 items-center gap-2 border-b border-border px-3">
          <h2 className="min-w-0 flex-1 truncate px-1 text-[13px] font-semibold text-text">
            {title}
          </h2>
          {actions}
          <IconButton ref={closeRef} onClick={onClose} aria-label="Close" title="Close">
            <X size={ICON_SIZE} strokeWidth={1.75} />
          </IconButton>
        </header>

        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>

        {footer && (
          <div className="shrink-0 border-t border-border px-4 py-3">{footer}</div>
        )}
      </div>
    </div>
  );
}
