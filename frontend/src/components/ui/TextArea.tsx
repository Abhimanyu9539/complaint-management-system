import { useId } from 'react';
import type { TextareaHTMLAttributes } from 'react';
import { Field } from './Field';
import { CONTROL_BASE, charactersLeft, controlBorder, describedBy } from '@/lib/forms';

interface TextAreaProps
  extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'value' | 'onChange' | 'id'> {
  label: string;
  value: string;
  onChange(value: string): void;
  hint?: string;
  error?: string;
  rows?: number;
  /** Shows a remaining-characters count as the limit approaches. */
  maxLength?: number;
}

/**
 * A multi-line text control with its label, hint, error and length budget.
 *
 * The counter appears only in the last quarter of the allowance
 * (`charactersLeft`). Shown from the first keystroke it reads as a word count to
 * hit; shown near the end it is a warning, which is the only time it is useful.
 */
export function TextArea({
  label,
  value,
  onChange,
  hint,
  error,
  required = false,
  rows = 6,
  maxLength,
  className = '',
  ...props
}: TextAreaProps) {
  const id = useId();
  const remaining = maxLength ? charactersLeft(value, maxLength) : null;

  return (
    <Field htmlFor={id} label={label} hint={hint} error={error} required={required}>
      <div className="relative">
        <textarea
          id={id}
          value={value}
          rows={rows}
          maxLength={maxLength}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(id, Boolean(hint), Boolean(error))}
          aria-required={required || undefined}
          className={`resize-y px-2.5 py-2 leading-relaxed ${CONTROL_BASE} ${controlBorder(Boolean(error))} ${className}`}
          {...props}
        />
        {remaining !== null && (
          // aria-live so the count is announced as it changes, but `polite` so
          // it waits for a pause rather than interrupting every keystroke.
          <span
            aria-live="polite"
            className={`pointer-events-none absolute right-2 bottom-2 rounded bg-bg-elevated px-1 text-[10px] tabular-nums ${
              remaining <= 0 ? 'text-danger' : 'text-text-faint'
            }`}
          >
            {remaining} left
          </span>
        )}
      </div>
    </Field>
  );
}
