/**
 * Form helpers shared by the input primitives.
 *
 * Here rather than beside `Field` for the same reason `status.ts` is not beside
 * `StatusPill`: oxlint's `react/only-export-components` forbids a component
 * module from exporting helper functions.
 */

/** The classes every text control shares, so an input and a textarea match. */
export const CONTROL_BASE =
  'w-full rounded-lg border bg-bg-elevated text-[13px] text-text transition-colors ' +
  'placeholder:text-text-faint disabled:cursor-not-allowed disabled:opacity-50';

/**
 * Border classes for a control, by validity.
 *
 * Literal strings on both branches — Tailwind's scanner reads source text, so a
 * class assembled from a variable is a class that was never compiled.
 */
export function controlBorder(hasError: boolean): string {
  return hasError
    ? 'border-danger hover:border-danger'
    : 'border-border hover:border-border-strong';
}

/**
 * The `aria-describedby` value for a control rendered inside a `Field`.
 *
 * Returns `undefined` rather than `''` when there is nothing to describe: an
 * empty `aria-describedby` resolves to no element, and a control that points at
 * nothing is worse than one that points nowhere.
 *
 * Error wins over hint because `Field` hides the hint while an error shows —
 * describing a paragraph that is not rendered would announce stale advice.
 */
export function describedBy(id: string, hasHint: boolean, hasError: boolean): string | undefined {
  if (hasError) return `${id}-error`;
  if (hasHint) return `${id}-hint`;
  return undefined;
}

/**
 * Characters remaining against a limit, or null when the count should stay
 * hidden.
 *
 * A counter that is visible from the first keystroke reads as a target. This
 * shows it only in the last quarter of the budget, which is when it becomes
 * information rather than pressure.
 */
export function charactersLeft(value: string, max: number): number | null {
  const remaining = max - value.length;
  return remaining <= max / 4 ? remaining : null;
}
