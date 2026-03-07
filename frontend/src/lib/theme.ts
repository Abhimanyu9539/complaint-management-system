export type ThemePreference = 'light' | 'dark' | null;

const THEME_KEY = 'cms.theme';

export function readStoredTheme(): ThemePreference {
  try {
    const raw = localStorage.getItem(THEME_KEY);
    if (raw === 'light' || raw === 'dark') return raw;
    return null;
  } catch {
    return null;
  }
}

export function writeStoredTheme(theme: ThemePreference): void {
  try {
    if (theme === null) {
      localStorage.removeItem(THEME_KEY);
    } else {
      localStorage.setItem(THEME_KEY, theme);
    }
  } catch {
    // storage unavailable (private browsing, quota) — theme just won't persist
  }
}

export function systemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

export function resolveIsDark(preference: ThemePreference): boolean {
  return preference === 'dark' || (preference === null && systemPrefersDark());
}

export function applyThemeClass(isDark: boolean): void {
  document.documentElement.classList.toggle('dark', isDark);
}
