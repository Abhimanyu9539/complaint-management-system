import { Loader2 } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md';
  /** Swaps the leading icon for a spinner and disables the button. */
  loading?: boolean;
  /** A lucide icon, rendered before the label. */
  icon?: ReactNode;
  children: ReactNode;
}

const VARIANTS: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary: 'bg-accent text-accent-text hover:bg-accent-strong border border-transparent',
  secondary:
    'border border-border bg-bg-elevated text-text shadow-sm hover:border-border-strong hover:bg-surface-hover',
  ghost: 'border border-transparent text-text-muted hover:bg-surface-hover hover:text-text',
  danger: 'border border-danger/30 bg-danger-soft text-danger hover:border-danger/50',
};

const SIZES: Record<NonNullable<ButtonProps['size']>, string> = {
  sm: 'h-8 gap-1.5 px-2.5 text-[12px]',
  md: 'h-9 gap-2 px-3 text-[13px]',
};

/**
 * The panel's text button.
 *
 * Note that the existing hand-rolled "New chat" button in the chat sidebar is
 * deliberately *not* refactored onto this. It is one button, it already works,
 * and rewriting it buys nothing while risking the one screen users actually
 * have today.
 */
export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  className = '',
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={`inline-flex shrink-0 items-center justify-center rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${SIZES[size]} ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {loading ? <Loader2 size={14} strokeWidth={2} className="animate-spin" /> : icon}
      {children}
    </button>
  );
}
