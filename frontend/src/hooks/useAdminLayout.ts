import { useOutletContext } from 'react-router';

interface AdminOutletContext {
  /** Opens the slide-over navigation. Only meaningful below the md breakpoint. */
  openMobileNav(): void;
}

/**
 * Access to the layout route's controls from inside a page.
 *
 * Each admin page renders its own header rail (so the actions in it belong to
 * the page), which means the mobile nav toggle has to reach back up to the
 * shell that owns the drawer state.
 */
export function useAdminLayout(): AdminOutletContext {
  return useOutletContext<AdminOutletContext>();
}
