import { DEFAULT_PALETTE, isPaletteId, type PaletteId } from './palettes';

export type ThemePreference = 'light' | 'dark' | null;

const THEME_KEY = 'cms.theme';
const PALETTE_KEY = 'cms.palette';
const SURFACE_KEY = 'cms.surface';

/** 'neutral' keeps backgrounds grey and shows the palette only on accents. */
export type SurfaceMode = 'neutral' | 'tinted';

export const DEFAULT_SURFACE: SurfaceMode = 'neutral';

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

export function readStoredSurface(): SurfaceMode {
  try {
    const raw = localStorage.getItem(SURFACE_KEY);
    return raw === 'tinted' || raw === 'neutral' ? raw : DEFAULT_SURFACE;
  } catch {
    return DEFAULT_SURFACE;
  }
}

export function writeStoredSurface(surface: SurfaceMode): void {
  try {
    localStorage.setItem(SURFACE_KEY, surface);
  } catch {
    // storage unavailable — surface mode just won't persist
  }
}

export function applySurfaceAttribute(surface: SurfaceMode): void {
  document.documentElement.setAttribute('data-surface', surface);
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
