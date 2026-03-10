import type { ReactNode } from 'react';

interface FieldProps {
  /** The `id` of the control this labels. Callers own it so `useId` is called once. */
  htmlFor: string;
  label: string;
  /** Standing guidance — what to type. Always visible. */
  hint?: string;
  /** Validation message. Replaces the hint's slot and colours the control. */
  error?: string;
  /** Marks the label and sets `aria-required` on the caller's control. */
  required?: boolean;
  children: ReactNode;
  className?: string;
}

/**
 * Label, hint and error around one form control.
 *
 * Exists because the accessible wiring is the part that gets skipped: the hint
 * and the error both have to be reachable from the input via
 * `aria-describedby`, and the ids have to be derived from the control's own id
 * or they collide the moment two fields render. Doing that once here is the
 * difference between a form that a screen reader can complete and one where the
 * error is invisible to it.
 *
 * The caller passes `htmlFor` rather than this component generating an id,
 * because the control also needs `aria-describedby={describedBy(id, …)}` and
 * both halves must agree. One owner for the id, no coordination problem.
 */
export function Field({
  htmlFor,
  label,
  hint,
  error,
  required = false,
  children,
  className = '',
}: FieldProps) {
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <label
        htmlFor={htmlFor}
        className="text-[11px] font-semibold tracking-[0.08em] text-text-faint uppercase"
      >
        {label}
        {required && (
          <span className="ml-1 text-danger" aria-hidden="true">
            *
          </span>
        )}
      </label>

      {children}

      {/*
        `role="alert"` so a screen reader announces a validation failure that
        appears after submit, when focus has not moved to the field. The hint is
        hidden while an error shows: two lines of competing advice under one
        input is how a form gets ignored.
      */}
      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-[11px] leading-relaxed text-danger">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${htmlFor}-hint`} className="text-[11px] leading-relaxed text-text-faint">
            {hint}
          </p>
        )
      )}
    </div>
  );
}
