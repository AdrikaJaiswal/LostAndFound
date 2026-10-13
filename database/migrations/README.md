# Return workflow migration draft

`20261013_001_record_item_return.sql` is a review draft. It has not been
executed against a database. The repository has no existing migration runner or
naming convention; this timestamped file is a local convention for review.

## Decisions required before deployment

- Developer 1 must confirm a server-only credential and database role for the
  Flask RPC. The migration revokes execution from `PUBLIC`, `anon`,
  `authenticated`, and `service_role`, and intentionally grants no role. Do
  not enable the endpoint against a database until an explicitly approved
  least-privilege grant is added. The README currently calls `SUPABASE_KEY` an
  anon key; that key will not be able to execute this function after the
  revokes. A `service_role` key bypasses RLS, so do not use it without explicit
  approval; if approved, it must remain server-only, be supplied outside source
  control, and be used only by the Flask backend. Prefer a dedicated backend
  database role with only the necessary table/function privileges if the team
  can support it. For a dedicated `SECURITY INVOKER` caller, the required table
  privileges are `SELECT` on `users`, `roles`, `claims`, `items`, and
  `returned_items`, `INSERT` on `returned_items`, `UPDATE(status)` on `items`,
  and `USAGE` on the `returned_items_return_id_seq` sequence, in addition to
  `EXECUTE` on the function. Confirm whether those table privileges and the
  Supabase API role setup are acceptable before granting access.
- `users.department` is not confirmed as the academic programme. The RPC
  requires an explicit `claimant_programme` value and stores it as a snapshot;
  the source and verification procedure for that value still need team
  confirmation.
- The function does not change other pending or approved claims for the same
  item. The team has not decided whether those claims should be rejected or
  flagged after one claim is returned.

## Disposable local integration test

Do not use a shared/hosted Supabase project or a production URL. First create or
start a disposable **local Supabase/PostgreSQL** instance that includes the
Supabase roles `anon` and `authenticated`. Confirm its database host is local
(`localhost`/`127.0.0.1`) and that its data can safely be discarded. This repo
does not include a Supabase CLI config or migration runner, so the team must
provide the local instance and SQL client separately.

1. Apply `database/schema.sql` to the disposable database, then apply
   `database/migrations/20261013_001_record_item_return.sql` using the local
   SQL client. Do not substitute any shared Supabase URL or credentials.
2. Insert fixture users with Student, Faculty, and Admin roles; insert items
   in each status (`Available`, `Claimed`, `Returned`, `Archived`); and insert
   claims in `Approved`, `Pending`, and `Rejected` states. Keep all fixture
   IDs and test inputs local.
3. As the migration owner (the migration deliberately grants no client role),
   call `public.record_item_return` with an approved claim and valid receiver
   values. Verify the returned row has the selected item/claim, verifier,
   receiver snapshot, and notes, and that the item's status changed to
   `Returned`.
4. Verify a missing claim and a non-approved claim fail without creating a
   return. Try an `Available` and a `Claimed` item (both should succeed with
   separate fixtures); try `Returned` and `Archived` items (both should fail).
5. For duplicate coverage, retry the same claim and also try a second approved
   claim for an item that already has a return. Verify no second return row is
   created and the item remains `Returned`.
6. Verify field validation at the RPC boundary: null/blank receiver values,
   registration number longer than 30 characters, phone longer than 15,
   programme longer than 100, and notes longer than 10,000 must fail.
7. Verify rollback in a disposable transaction by adding a temporary local-only
   trigger that raises an exception when `items.status` is updated to
   `Returned`. Call the function and confirm both the `returned_items` insert
   and item-status change are absent after the error. Drop the temporary
   trigger/function afterward. Never add this test trigger to a shared database.
8. For concurrency, create two approved claims for one `Available` item and run
   two function calls simultaneously from separate local database sessions.
   Confirm exactly one return row exists for the item and its status is
   `Returned`; the competing request should fail with a conflict. Repeat with
   two concurrent calls for the same claim.
9. Check function privileges before any application integration: the function
   must not be executable by `PUBLIC`, `anon`, `authenticated`, or
   `service_role` unless Developer 1 explicitly approves a different policy.
   Only after Developer 1 approves the backend credential and grant should the
   local Flask route be integration-tested using that local credential.

The Python `unittest` suite mocks Supabase and verifies the Flask-to-RPC
contract. It cannot prove PostgreSQL transaction rollback, locks, grants, or
concurrent behavior; those require the disposable local database tests above.
