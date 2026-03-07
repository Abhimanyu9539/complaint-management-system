import { useCallback, useEffect, useState } from 'react';
import {
  applyThemeClass,
  readStoredTheme,
  resolveIsDark,
  writeStoredTheme,
  type ThemePreference,
} from '@/lib/theme';

export function useTheme() {
  const [preference, setPreference] = useState<ThemePreference>(() => readStoredTheme());
  const [isDark, setIsDark] = useState(() => resolveIsDark(readStoredTheme()));

  useEffect(() => {
    applyThemeClass(isDark);
  }, [isDark]);

  useEffect(() => {
    if (preference !== null) return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => setIsDark(resolveIsDark(null));
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [preference]);

  const toggle = useCallback(() => {
    setPreference((prev) => {
      const next: ThemePreference = resolveIsDark(prev) ? 'light' : 'dark';
      writeStoredTheme(next);
      setIsDark(resolveIsDark(next));
      return next;
    });
  }, []);

  return { isDark, toggle };
}
