import { MessageSquare } from 'lucide-react';
import type { SessionMeta } from '@/lib/chat/types';

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

interface SessionItemProps {
  session: SessionMeta;
  active: boolean;
  onSelect(): void;
}

export function SessionItem({ session, active, onSelect }: SessionItemProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`group relative flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left transition-colors ${
        active
          ? 'bg-accent-soft text-text'
          : 'text-text-muted hover:bg-surface-hover hover:text-text'
      }`}
    >
      {active && (
        <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-full bg-accent" />
      )}
      <MessageSquare
        size={15}
        strokeWidth={1.75}
        className={active ? 'text-accent' : 'text-text-faint group-hover:text-text-muted'}
      />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] leading-tight font-medium">
          {session.title}
        </span>
        <span className="block truncate text-[11px] text-text-faint">
          {relativeTime(session.updatedAt)}
        </span>
      </span>
    </button>
  );
}
