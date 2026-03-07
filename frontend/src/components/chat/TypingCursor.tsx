export function TypingCursor() {
  return (
    <span
      className="ml-0.5 inline-block h-[1em] w-[2px] translate-y-[2px] bg-accent align-middle"
      style={{ animation: 'blink-caret 1s step-end infinite' }}
    />
  );
}

export function ThinkingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-text-faint"
          style={{
            animation: 'blink-caret 1.1s ease-in-out infinite',
            animationDelay: `${i * 0.15}s`,
          }}
        />
      ))}
    </span>
  );
}
