import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

const OPEN_KEY = 'cms.sources.open';

function readStoredOpen(): boolean {
  try {
    const raw = localStorage.getItem(OPEN_KEY);
    return raw === null ? true : raw === 'true';
  } catch {
    return true;
  }
}

interface CitationsPanelValue {
  /** Desktop inline column; persisted across reloads. */
  isOpen: boolean;
  /** Mobile/tablet slide-over; session-only so a fresh load never covers a phone screen. */
  isMobileOpen: boolean;
  /** Reveals the desktop rail. */
  expand(): void;
  /** Reveals the small-screen slide-over. */
  openMobile(): void;
  close(): void;
  /** Message whose sources are pinned in the panel; null means "follow the latest answer". */
  pinnedMessageId: string | null;
  focusedChunkId: string | null;
  showFor(messageId: string, focusChunkId?: string): void;
  clearPin(): void;
}

const CitationsPanelContext = createContext<CitationsPanelValue | null>(null);

export function CitationsPanelProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(readStoredOpen);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [pinnedMessageId, setPinnedMessageId] = useState<string | null>(null);
  const [focusedChunkId, setFocusedChunkId] = useState<string | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(OPEN_KEY, String(isOpen));
    } catch {
      // storage unavailable — panel state just won't persist
    }
  }, [isOpen]);

  const expand = useCallback(() => setIsOpen(true), []);
  const openMobile = useCallback(() => setIsMobileOpen(true), []);

  const close = useCallback(() => {
    setIsOpen(false);
    setIsMobileOpen(false);
  }, []);

  const showFor = useCallback((messageId: string, focusChunkId?: string) => {
    setPinnedMessageId(messageId);
    setFocusedChunkId(focusChunkId ?? null);
    setIsOpen(true);
    setIsMobileOpen(true);
  }, []);

  const clearPin = useCallback(() => {
    setPinnedMessageId(null);
    setFocusedChunkId(null);
  }, []);

  const value = useMemo<CitationsPanelValue>(
    () => ({
      isOpen,
      isMobileOpen,
      expand,
      openMobile,
      close,
      pinnedMessageId,
      focusedChunkId,
      showFor,
      clearPin,
    }),
    [
      isOpen,
      isMobileOpen,
      expand,
      openMobile,
      close,
      pinnedMessageId,
      focusedChunkId,
      showFor,
      clearPin,
    ],
  );

  return (
    <CitationsPanelContext.Provider value={value}>{children}</CitationsPanelContext.Provider>
  );
}

export function useCitationsPanel(): CitationsPanelValue {
  const ctx = useContext(CitationsPanelContext);
  if (!ctx) throw new Error('useCitationsPanel must be used within a CitationsPanelProvider');
  return ctx;
}
