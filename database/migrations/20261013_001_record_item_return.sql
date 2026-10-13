-- Draft migration: review and test on a disposable local Supabase database.
-- This file has not been applied to any database.
--
-- `users.department` is not confirmed to be the claimant's academic programme.
-- The caller must provide a separately verified claimant_programme snapshot.
--
-- No execution role is granted below. Developer 1 must approve the server key,
-- database role, and least-privilege grants before enabling the Flask RPC call.

BEGIN;

ALTER TABLE public.returned_items
    ADD COLUMN IF NOT EXISTS claimant_programme VARCHAR(100);

CREATE OR REPLACE FUNCTION public.record_item_return(
    p_claim_id INTEGER,
    p_verified_by_faculty_id INTEGER,
    p_claimant_registration_no TEXT,
    p_claimant_phone TEXT,
    p_claimant_programme TEXT,
    p_verification_notes TEXT DEFAULT NULL
)
RETURNS SETOF public.returned_items
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $function$
DECLARE
    v_claim public.claims%ROWTYPE;
    v_item public.items%ROWTYPE;
    v_return public.returned_items%ROWTYPE;
    v_updated_rows INTEGER;
BEGIN
    IF p_claimant_registration_no IS NULL
       OR p_claimant_registration_no ~ '^[[:space:]]*$'
       OR char_length(p_claimant_registration_no) > 30
       OR p_claimant_phone IS NULL
       OR p_claimant_phone ~ '^[[:space:]]*$'
       OR char_length(p_claimant_phone) > 15
       OR p_claimant_programme IS NULL
       OR p_claimant_programme ~ '^[[:space:]]*$'
       OR char_length(p_claimant_programme) > 100
       OR (p_verification_notes IS NOT NULL
           AND char_length(p_verification_notes) > 10000) THEN
        RAISE EXCEPTION USING
            ERRCODE = '22023',
            MESSAGE = 'invalid_return_details';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM public.users AS verifier
        JOIN public.roles AS verifier_role
          ON verifier_role.role_id = verifier.role_id
        WHERE verifier.user_id = p_verified_by_faculty_id
          AND verifier_role.role_name IN ('Faculty', 'Admin')
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '42501',
            MESSAGE = 'invalid_return_verifier';
    END IF;

    SELECT claim.*
    INTO v_claim
    FROM public.claims AS claim
    WHERE claim.claim_id = p_claim_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION USING
            ERRCODE = 'P0002',
            MESSAGE = 'claim_not_found';
    END IF;

    IF v_claim.claim_status <> 'Approved' THEN
        RAISE EXCEPTION USING
            ERRCODE = 'P0001',
            MESSAGE = 'claim_not_approved';
    END IF;

    SELECT item.*
    INTO v_item
    FROM public.items AS item
    WHERE item.item_id = v_claim.item_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION USING
            ERRCODE = 'P0002',
            MESSAGE = 'item_not_found';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.returned_items AS returned
        WHERE returned.item_id = v_item.item_id
           OR returned.claim_id = v_claim.claim_id
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = 'P0001',
            MESSAGE = 'return_already_recorded';
    END IF;

    IF v_item.status NOT IN ('Available', 'Claimed') THEN
        RAISE EXCEPTION USING
            ERRCODE = 'P0001',
            MESSAGE = 'item_not_returnable';
    END IF;

    INSERT INTO public.returned_items (
        item_id,
        claim_id,
        verified_by_faculty_id,
        claimant_registration_no,
        claimant_phone,
        claimant_programme,
        verification_notes
    )
    VALUES (
        v_item.item_id,
        v_claim.claim_id,
        p_verified_by_faculty_id,
        btrim(p_claimant_registration_no),
        btrim(p_claimant_phone),
        btrim(p_claimant_programme),
        p_verification_notes
    )
    RETURNING * INTO v_return;

    UPDATE public.items
    SET status = 'Returned'
    WHERE item_id = v_item.item_id
      AND status IN ('Available', 'Claimed');

    GET DIAGNOSTICS v_updated_rows = ROW_COUNT;
    IF v_updated_rows <> 1 THEN
        RAISE EXCEPTION USING
            ERRCODE = 'P0001',
            MESSAGE = 'item_not_returnable';
    END IF;

    RETURN NEXT v_return;
    RETURN;
END;
$function$;

-- Remove PostgreSQL's default PUBLIC execute privilege and any broad Supabase
-- client-role grants. Do not grant service_role until the server credential,
-- RLS bypass implications, and least-privilege policy are approved.
REVOKE ALL PRIVILEGES ON FUNCTION public.record_item_return(
    INTEGER, INTEGER, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC, anon, authenticated, service_role;

COMMIT;
