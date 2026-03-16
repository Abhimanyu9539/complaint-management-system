-- 0018_policy_files_bucket.sql — the Storage bucket policy files upload into.
--
-- Supersedes the "NULL for seed-from-disk" comment on policies.storage_path in
-- 0006_policies.sql:33 (that file already shipped and cannot be edited): seed
-- policies are now uploaded too, so storage_path is populated for every row.
--
-- `insert into storage.buckets` runs fine as a plain migration even though the
-- `storage` schema is owned by `supabase_storage_admin` — the SQL editor (and
-- `db push`) runs as `postgres`, which has full DML rights there. That grant
-- does NOT extend to `CREATE POLICY`, which is why this file deliberately adds
-- none: every access to this bucket goes through the backend's service-role
-- client (cms/db/session.py), never a browser, so storage.objects RLS is not
-- needed. Add policies later only if browsers start talking to Storage
-- directly, and expect to deal with ownership then.
--
-- `on conflict ... do update` rather than `do nothing`, so a re-run still
-- applies config changes (matches intent, not `0003_departments.sql`'s
-- `do nothing`, which has the same latent staleness problem).
--
-- No `allowed_mime_types`: NULL means "any", which keeps the door open for a
-- future non-markdown upload (PDF, docx) without another migration.

insert into storage.buckets (id, name, public, file_size_limit)
values ('policy-files', 'policy-files', false, 5242880)
on conflict (id) do update
    set public          = excluded.public,
        file_size_limit = excluded.file_size_limit;
