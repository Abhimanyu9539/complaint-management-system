import { Moon, Sun } from 'lucide-react';
import { ICON_SIZE, IconButton } from '@/components/ui/IconButton';
import { useTheme } from '@/state/ThemeProvider';

export function ThemeToggle() {
  const { isDark, toggleTheme } = useTheme();

  return (
    <IconButton
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className="relative"
    >
      <Sun
        size={ICON_SIZE}
        strokeWidth={1.75}
        className={`absolute transition-all duration-300 ${isDark ? 'scale-0 -rotate-90 opacity-0' : 'scale-100 rotate-0 opacity-100'}`}
      />
      <Moon
        size={ICON_SIZE}
        strokeWidth={1.75}
        className={`absolute transition-all duration-300 ${isDark ? 'scale-100 rotate-0 opacity-100' : 'scale-0 rotate-90 opacity-0'}`}
      />
    </IconButton>
  );
}
