import { Eye, EyeOff } from 'lucide-react';
import { useId, useState } from 'react';
import type { InputHTMLAttributes, KeyboardEvent, Ref } from 'react';
import { Field } from './Field';
import { CONTROL_BASE, controlBorder, describedBy } from '@/lib/forms';

interface PasswordInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange' | 'id' | 'type'> {
  label: string;
  value: string;
  onChange(value: string): void;
  error?: string;
  ref?: Ref<HTMLInputElement>;
}

/** `TextInput` for passwords: a show/hide toggle, and a hint while Caps Lock is on. */
export function PasswordInput({
  label,
  value,
  onChange,
  error,
  required = false,
  className = '',
  ...props
}: PasswordInputProps) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const hint = capsLock ? 'Caps Lock is on.' : undefined;

  function checkCapsLock(event: KeyboardEvent<HTMLInputElement>) {
    setCapsLock(event.getModifierState('CapsLock'));
  }

  return (
    <Field htmlFor={id} label={label} hint={hint} error={error} required={required}>
      <div className="relative">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={checkCapsLock}
          onKeyUp={checkCapsLock}
          onBlur={() => setCapsLock(false)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(id, Boolean(hint), Boolean(error))}
          aria-required={required || undefined}
          className={`h-9 pr-10 pl-2.5 ${CONTROL_BASE} ${controlBorder(Boolean(error))} ${className}`}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((shown) => !shown)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-controls={id}
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center rounded-r-lg text-text-muted transition-colors hover:text-text"
        >
          {visible ? <EyeOff size={16} strokeWidth={1.75} /> : <Eye size={16} strokeWidth={1.75} />}
        </button>
      </div>
    </Field>
  );
}
