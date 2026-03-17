import { Bot } from 'lucide-react';
import { AdminPageHeader } from '@/components/admin/layout/AdminShell';
import { LiveIndicator } from '@/components/admin/layout/LiveIndicator';
import { EmptyState } from '@/components/ui/EmptyState';
import { Panel } from '@/components/ui/Panel';
import { useAdminLayout } from '@/hooks/useAdminLayout';

/**
 * Agent activity. There is no agent yet — the RAG graph in lld.md §6
 * (analyze_query → retrieve → grade_documents → generate → check_groundedness)
 * has not been built, so there is nothing to log. Kept as a real page with an
 * honest empty state, rather than fabricated rows, so the nav entry stays
 * meaningful and this becomes the first thing to update once the graph runs.
 * See `backend/docs/admin-api.md` §6.
 */
export function ActivityPage() {
  const { openMobileNav } = useAdminLayout();

  return (
    <>
      <AdminPageHeader
        title="Agent activity"
        description="Graph executions, routing decisions and latency"
        onOpenNav={openMobileNav}
        actions={<LiveIndicator />}
      />

      <div className="flex flex-col gap-4 p-4">
        <Panel title="Execution history" eyebrow="Runs">
          <EmptyState
            icon={<Bot size={18} strokeWidth={1.5} />}
            title="No agent runs recorded"
            description="The RAG graph hasn't been built yet, so nothing produces runs to show here. This page will populate once it's instrumented — see backend/docs/admin-api.md §6."
          />
        </Panel>
      </div>
    </>
  );
}
