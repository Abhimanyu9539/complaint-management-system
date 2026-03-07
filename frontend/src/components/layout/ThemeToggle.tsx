import { Moon, Sun } from 'lucide-react';
import { useTheme } from '@/state/ThemeProvider';

export function ThemeToggle() {
  const { isDark, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className="relative inline-flex h-8 w-8 items-center justify-center rounded-full text-text-muted transition-colors hover:bg-surface-hover hover:text-text"
    >
      <Sun
        size={17}
        strokeWidth={1.75}
        className={`absolute transition-all duration-300 ${isDark ? 'scale-0 -rotate-90 opacity-0' : 'scale-100 rotate-0 opacity-100'}`}
      />
      <Moon
        size={16}
        strokeWidth={1.75}
        className={`absolute transition-all duration-300 ${isDark ? 'scale-100 rotate-0 opacity-100' : 'scale-0 rotate-90 opacity-0'}`}
      />
    </button>
  );
}
