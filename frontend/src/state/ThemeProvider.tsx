import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { PaletteId } from '@/lib/palettes';
import {
  applyPaletteAttribute,
  applyThemeClass,
  readStoredPalette,
  readStoredTheme,
  resolveIsDark,
  writeStoredPalette,
  writeStoredTheme,
  type ThemePreference,
} from '@/lib/theme';

interface ThemeContextValue {
  isDark: boolean;
  toggleTheme(): void;
  palette: PaletteId;
  setPalette(palette: PaletteId): void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreference] = useState<ThemePreference>(() => readStoredTheme());
  const [isDark, setIsDark] = useState(() => resolveIsDark(readStoredTheme()));
  const [palette, setPaletteState] = useState<PaletteId>(() => readStoredPalette());

  useEffect(() => {
    applyThemeClass(isDark);
  }, [isDark]);

  useEffect(() => {
    applyPaletteAttribute(palette);
  }, [palette]);

  // While no explicit preference is stored, follow the OS setting live.
  useEffect(() => {
    if (preference !== null) return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => setIsDark(resolveIsDark(null));
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [preference]);

  const toggleTheme = useCallback(() => {
    setPreference((prev) => {
      const next: ThemePreference = resolveIsDark(prev) ? 'light' : 'dark';
      writeStoredTheme(next);
      setIsDark(resolveIsDark(next));
      return next;
    });
  }, []);

  const setPalette = useCallback((next: PaletteId) => {
    writeStoredPalette(next);
    setPaletteState(next);
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({ isDark, toggleTheme, palette, setPalette }),
    [isDark, toggleTheme, palette, setPalette],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}
