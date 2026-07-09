import { Check, Copy } from 'lucide-react';
import { useState } from 'react';
import { IconButton } from '@/components/ui/IconButton';

/** Small building blocks shared by the admin drawers. */

export function SectionLabel({ children }: { children: string }) {
  return (
    <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
      {children}
    </h3>
  );
}

export function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="shrink-0 text-[11px] text-text-faint">{label}</span>
      <span className={`min-w-0 truncate text-[12.5px] text-text ${mono ? 'font-mono' : ''}`}>
        {value}
      </span>
    </div>
  );
}

/** A monospace value with a copy button — run ids exist to be pasted elsewhere. */
export function CopyableValue({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard
      ?.writeText(value)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1600);
      })
      .catch(() => {
        // Clipboard blocked (insecure origin, or permission denied). The value
        // is on screen and selectable, so this degrades to manual copying.
        console.warn('Clipboard write failed; the value is still selectable.');
      });
  };

  return (
    <div className="flex items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-2.5 py-1.5">
      <code className="min-w-0 flex-1 truncate font-mono text-[11.5px] text-text-muted">
        {value}
      </code>
      <IconButton onClick={copy} aria-label="Copy" title="Copy" className="h-6 w-6">
        {copied ? (
          <Check size={12} strokeWidth={2.5} className="text-ok" />
        ) : (
          <Copy size={12} strokeWidth={2} />
        )}
      </IconButton>
    </div>
  );
}
