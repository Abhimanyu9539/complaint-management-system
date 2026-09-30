interface BrandMarkProps {
  /** The area name beside the "R" mark: Resolvr, Admin, Support. */
  label?: string;
  className?: string;
}

/** The "R" logo and area name at the top of every page. */
export function BrandMark({ label = 'Resolvr', className = '' }: BrandMarkProps) {
  return (
    <div className={`flex min-w-0 items-center gap-2 ${className}`}>
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent text-accent-text">
        <span className="font-display text-[13px] leading-none" aria-hidden="true">
          R
        </span>
      </div>
      <span className="truncate font-display text-[14px] font-medium text-text">{label}</span>
    </div>
  );
}
