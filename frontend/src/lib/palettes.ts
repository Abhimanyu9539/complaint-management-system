export const PALETTES = [
  { id: 'violet', label: 'Violet', swatch: { light: '#7c3aed', dark: '#a78bfa' } },
  { id: 'ocean', label: 'Ocean', swatch: { light: '#0284c7', dark: '#38bdf8' } },
  { id: 'emerald', label: 'Emerald', swatch: { light: '#0f8a5f', dark: '#34d399' } },
  { id: 'rose', label: 'Rose', swatch: { light: '#e11d48', dark: '#fb7185' } },
  { id: 'ember', label: 'Ember', swatch: { light: '#c4562b', dark: '#e0824a' } },
  { id: 'graphite', label: 'Graphite', swatch: { light: '#18181b', dark: '#fafafa' } },
] as const;

export type PaletteId = (typeof PALETTES)[number]['id'];

export const DEFAULT_PALETTE: PaletteId = 'violet';

const PALETTE_IDS = PALETTES.map((p) => p.id) as readonly string[];

export function isPaletteId(value: unknown): value is PaletteId {
  return typeof value === 'string' && PALETTE_IDS.includes(value);
}
