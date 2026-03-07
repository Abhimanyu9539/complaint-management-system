import { PALETTES } from '@/lib/palettes';
import { useTheme } from '@/state/ThemeProvider';

export function PalettePicker() {
  const { palette, setPalette, isDark, surface, toggleSurface } = useTheme();
  const tinted = surface === 'tinted';

  return (
    <div className="px-4 py-3">
      <div className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
        Colour
      </div>

      <div className="flex items-center gap-2">
        {PALETTES.map((option) => {
          const color = isDark ? option.swatch.dark : option.swatch.light;
          const active = option.id === palette;
          return (
            <button
              key={option.id}
              type="button"
              onClick={() => setPalette(option.id)}
              title={option.label}
              aria-label={`${option.label} colour scheme`}
              aria-pressed={active}
              className="h-5 w-5 rounded-full transition-transform duration-150 hover:scale-115"
              style={{
                backgroundColor: color,
                boxShadow: active
                  ? `0 0 0 2px var(--surface), 0 0 0 4px ${color}`
                  : 'inset 0 0 0 1px rgb(0 0 0 / 0.12)',
              }}
            />
          );
        })}
      </div>

      <button
        type="button"
        role="switch"
        aria-checked={tinted}
        onClick={toggleSurface}
        title="Tint backgrounds with the accent colour instead of keeping them neutral"
        className="mt-3 flex w-full items-center justify-between gap-2 rounded-lg py-1 text-left transition-colors"
      >
        <span className="text-[12px] text-text-muted">Tinted surfaces</span>
        <span
          className={`relative h-4 w-7 shrink-0 rounded-full transition-colors ${
            tinted ? 'bg-accent' : 'bg-border-strong'
          }`}
        >
          <span
            className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-transform ${
              tinted ? 'translate-x-3.5' : 'translate-x-0.5'
            }`}
          />
        </span>
      </button>
    </div>
  );
}
