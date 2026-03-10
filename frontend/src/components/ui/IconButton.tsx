import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react';

/** Single source of truth for control sizing, so every toolbar button lines up. */
export const ICON_SIZE = 16;

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  /** Pill with a text label instead of a fixed square. */
  withLabel?: boolean;
  /**
   * React 19 passes `ref` as an ordinary prop to function components, so no
   * forwardRef wrapper is needed. Declared explicitly because
   * `ButtonHTMLAttributes` does not include it. Used by `Drawer`, which moves
   * focus to its close button on open.
   */
  ref?: Ref<HTMLButtonElement>;
  children: ReactNode;
}

export function IconButton({
  active = false,
  withLabel = false,
  className = '',
  children,
  ...props
}: IconButtonProps) {
  return (
    <button
      type="button"
      className={`inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-lg text-[12px] font-medium transition-colors ${
        withLabel ? 'px-2.5' : 'w-8'
      } ${
        active
          ? 'bg-accent-soft text-accent'
          : 'text-text-muted hover:bg-surface-hover hover:text-text'
      } ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
