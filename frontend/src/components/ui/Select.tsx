import { ChevronDown } from 'lucide-react';
import { useId } from 'react';

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  label: string;
  /** Renders the label to screen readers only — for filter bars where the options speak for themselves. */
  hideLabel?: boolean;
  value: string;
  options: SelectOption[];
  onChange(value: string): void;
  size?: 'sm' | 'md';
  disabled?: boolean;
  className?: string;
}

/**
 * A native `<select>` with the chrome restyled.
 *
 * Deliberately not a custom listbox. A bespoke dropdown is a week of keyboard
 * and ARIA work, degrades on touch devices, and a filter control gains nothing
 * from it — the native element already gives correct keyboard behaviour, type-
 * ahead, and the platform's own mobile picker.
 */
export function Select({
  label,
  hideLabel = false,
  value,
  options,
  onChange,
  size = 'sm',
  disabled = false,
  className = '',
}: SelectProps) {
  const id = useId();
  const height = size === 'sm' ? 'h-8 text-[12px]' : 'h-9 text-[13px]';

  return (
    <div className={`flex min-w-0 flex-col gap-1 ${className}`}>
      <label
        htmlFor={id}
        className={
          hideLabel
            ? 'sr-only'
            : 'text-[11px] font-semibold tracking-[0.08em] text-text-faint uppercase'
        }
      >
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          className={`w-full appearance-none rounded-lg border border-border bg-bg-elevated py-0 pr-8 pl-2.5 font-medium text-text transition-colors hover:border-border-strong disabled:cursor-not-allowed disabled:opacity-50 ${height}`}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown
          size={14}
          strokeWidth={1.75}
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-text-faint"
        />
      </div>
    </div>
  );
}
