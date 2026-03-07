import { DEFAULT_PALETTE, isPaletteId, type PaletteId } from './palettes';

export type ThemePreference = 'light' | 'dark' | null;

const THEME_KEY = 'cms.theme';
const PALETTE_KEY = 'cms.palette';

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

export function readStoredPalette(): PaletteId {
  try {
    const raw = localStorage.getItem(PALETTE_KEY);
    return isPaletteId(raw) ? raw : DEFAULT_PALETTE;
  } catch {
    return DEFAULT_PALETTE;
  }
}

export function writeStoredPalette(palette: PaletteId): void {
  try {
    localStorage.setItem(PALETTE_KEY, palette);
  } catch {
    // storage unavailable — palette just won't persist
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

export function applyPaletteAttribute(palette: PaletteId): void {
  document.documentElement.setAttribute('data-palette', palette);
}
