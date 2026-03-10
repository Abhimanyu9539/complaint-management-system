import { useId } from 'react';
import type { InputHTMLAttributes } from 'react';
import { Field } from './Field';
import { CONTROL_BASE, controlBorder, describedBy } from '@/lib/forms';

interface TextInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange' | 'id'> {
  label: string;
  value: string;
  onChange(value: string): void;
  hint?: string;
  error?: string;
}

/**
 * A single-line text control with its label, hint and error.
 *
 * `onChange` hands over the string rather than the event, matching `Select` and
 * `SearchInput` — a call site that has to reach through `event.target.value` for
 * a value it already asked for is boilerplate with a typo waiting in it.
 */
export function TextInput({
  label,
  value,
  onChange,
  hint,
  error,
  required = false,
  className = '',
  ...props
}: TextInputProps) {
  const id = useId();

  return (
    <Field htmlFor={id} label={label} hint={hint} error={error} required={required}>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, Boolean(hint), Boolean(error))}
        // `required` drives ARIA only. Native validation is deliberately not
        // used: the browser's bubble cannot be styled, disappears on the next
        // click, and is announced differently in every engine — the form owns
        // its own messages so they behave the same everywhere.
        aria-required={required || undefined}
        className={`h-9 px-2.5 ${CONTROL_BASE} ${controlBorder(Boolean(error))} ${className}`}
        {...props}
      />
    </Field>
  );
}
