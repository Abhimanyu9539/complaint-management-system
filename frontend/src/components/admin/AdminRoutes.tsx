import { Route, Routes } from 'react-router';
import { AdminShell } from './layout/AdminShell';
import { ActivityPage } from '@/pages/admin/ActivityPage';
import { DashboardPage } from '@/pages/admin/DashboardPage';
import { IngestionPage } from '@/pages/admin/IngestionPage';
import { StatisticsPage } from '@/pages/admin/StatisticsPage';
import { TicketsPage } from '@/pages/admin/TicketsPage';
import { NotFoundRoute } from '@/pages/NotFoundRoute';
import { AdminRefreshProvider } from '@/state/AdminRefreshProvider';

/**
 * The whole admin route tree, in one module.
 *
 * Kept as a single file so `React.lazy` has exactly one chunk boundary to split
 * on: the charts, the tables and four page trees are dead weight for someone
 * who only ever opens the chat.
 *
 * `AdminRefreshProvider` wraps the tree rather than each page so the polling
 * cadence, the pause switch and the refresh-everything token survive navigation
 * between admin sections.
 */
export function AdminRoutes() {
  return (
    <AdminRefreshProvider>
      <Routes>
        <Route element={<AdminShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="tickets" element={<TicketsPage />} />
          <Route path="ingestion" element={<IngestionPage />} />
          <Route path="activity" element={<ActivityPage />} />
          <Route path="stats" element={<StatisticsPage />} />
          <Route path="*" element={<NotFoundRoute />} />
        </Route>
      </Routes>
    </AdminRefreshProvider>
  );
}
