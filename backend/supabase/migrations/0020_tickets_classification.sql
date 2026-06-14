-- 0020_tickets_classification.sql — what the ticket graph's classifier writes
-- beyond the columns 0004 already has (predicted_dept, dept_confidence,
-- category, entities).
--
-- `suggested_severity` is separate from `severity` on purpose: automated
-- classification may suggest a severity but never set it (intake §7,
-- severity §5). `severity` stays what the customer chose until a person
-- confirms a change.
--
-- `dept_candidates` is the ranked list behind `predicted_dept`:
-- [{"department": "warranty", "score": 0.72}, ...], scores summing to 1. The
-- workbench shows the runner-ups as "Also considered".
--
-- Additive and re-runnable, like every file here.

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_severity TEXT
    CHECK (suggested_severity IN ('low', 'normal', 'high', 'critical'));

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS dept_candidates JSONB NOT NULL DEFAULT '[]'::jsonb;

-- No RLS changes. 0004's `tickets_all` policy covers rows, so new columns are
-- in scope the moment they exist.
