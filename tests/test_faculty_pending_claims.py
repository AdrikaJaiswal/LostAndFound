import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from flask import Flask


def load_faculty_routes():
    fake_config = ModuleType("config")
    fake_config.supabase = Mock()

    route_path = Path(__file__).resolve().parents[1] / "routes" / "faculty.py"
    spec = importlib.util.spec_from_file_location(
        "_faculty_routes_under_test",
        route_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load faculty routes from {route_path}")

    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"config": fake_config}):
        spec.loader.exec_module(module)

    return module


faculty_routes = load_faculty_routes()


class PendingClaimsRouteTests(unittest.TestCase):
    def setUp(self):
        self.query = Mock()
        self.query.select.return_value = self.query
        self.query.eq.return_value = self.query

        self.supabase = Mock()
        self.supabase.table.return_value = self.query
        supabase_patch = patch.object(faculty_routes, "supabase", self.supabase)
        supabase_patch.start()
        self.addCleanup(supabase_patch.stop)

        app = Flask(__name__)
        app.secret_key = "test-only"
        app.register_blueprint(faculty_routes.faculty_bp)
        self.client = app.test_client()

    def set_role(self, role):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = role

    def test_unauthenticated_request_returns_401(self):
        response = self.client.get("/api/faculty/claims/pending")

        self.assertEqual(response.status_code, 401)
        self.supabase.table.assert_not_called()

    def test_student_request_returns_403(self):
        self.set_role("Student")

        response = self.client.get("/api/faculty/claims/pending")

        self.assertEqual(response.status_code, 403)
        self.supabase.table.assert_not_called()

    def test_faculty_and_admin_receive_pending_claims(self):
        claims = [{"claim_id": 5, "claim_status": "Pending"}]
        self.query.execute.return_value = SimpleNamespace(data=claims)

        for role in ("Faculty", "Admin"):
            with self.subTest(role=role):
                self.set_role(role)
                response = self.client.get("/api/faculty/claims/pending")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.get_json(),
                    {"status": "Success", "claims": claims},
                )

        self.assertEqual(
            self.supabase.table.call_args_list,
            [call("claims"), call("claims")],
        )
        self.assertEqual(
            self.query.mock_calls,
            [
                call.select(
                    "*, items(item_id, title, description, item_type, status, "
                    "date_reported, categories(category_name), "
                    "locations(location_name)), "
                    "claimant:users!claims_claimant_id_fkey"
                    "(user_id, full_name, registration_no, department)"
                ),
                call.eq("claim_status", "Pending"),
                call.execute(),
                call.select(
                    "*, items(item_id, title, description, item_type, status, "
                    "date_reported, categories(category_name), "
                    "locations(location_name)), "
                    "claimant:users!claims_claimant_id_fkey"
                    "(user_id, full_name, registration_no, department)"
                ),
                call.eq("claim_status", "Pending"),
                call.execute(),
            ],
        )

    def test_database_error_returns_generic_500(self):
        self.query.execute.side_effect = RuntimeError("private database detail")
        self.set_role("Faculty")

        response = self.client.get("/api/faculty/claims/pending")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["status"], "Error")
        self.assertNotIn(
            "private database detail",
            response.get_data(as_text=True),
        )


class ClaimDecisionRouteTests(unittest.TestCase):
    def setUp(self):
        self.query = Mock()
        self.query.update.return_value = self.query
        self.query.select.return_value = self.query
        self.query.eq.return_value = self.query

        self.supabase = Mock()
        self.supabase.table.return_value = self.query
        supabase_patch = patch.object(faculty_routes, "supabase", self.supabase)
        supabase_patch.start()
        self.addCleanup(supabase_patch.stop)

        app = Flask(__name__)
        app.secret_key = "test-only"
        app.register_blueprint(faculty_routes.faculty_bp)
        self.client = app.test_client()

    def set_role(self, role, user_id=1):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def test_unauthenticated_request_returns_401(self):
        response = self.client.post(
            "/api/faculty/claims/5/decision",
            json={"decision": "Approved"},
        )

        self.assertEqual(response.status_code, 401)
        self.supabase.table.assert_not_called()

    def test_student_request_returns_403(self):
        self.set_role("Student")

        response = self.client.post(
            "/api/faculty/claims/5/decision",
            json={"decision": "Approved"},
        )

        self.assertEqual(response.status_code, 403)
        self.supabase.table.assert_not_called()

    def test_faculty_can_approve_pending_claim(self):
        claim = {
            "claim_id": 5,
            "claim_status": "Approved",
            "reviewed_by": 12,
            "review_remarks": "Ownership verified.",
        }
        self.query.execute.return_value = SimpleNamespace(data=[claim])
        self.set_role("Faculty", user_id=12)

        response = self.client.post(
            "/api/faculty/claims/5/decision",
            json={
                "decision": "Approved",
                "review_remarks": "Ownership verified.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"status": "Success", "claim": claim},
        )
        self.supabase.table.assert_called_once_with("claims")
        self.query.update.assert_called_once_with({
            "claim_status": "Approved",
            "reviewed_by": 12,
            "review_remarks": "Ownership verified.",
        })
        self.assertEqual(
            self.query.mock_calls,
            [
                call.update({
                    "claim_status": "Approved",
                    "reviewed_by": 12,
                    "review_remarks": "Ownership verified.",
                }),
                call.eq("claim_id", 5),
                call.eq("claim_status", "Pending"),
                call.select("*"),
                call.execute(),
            ],
        )

    def test_faculty_can_reject_pending_claim(self):
        claim = {
            "claim_id": 5,
            "claim_status": "Rejected",
            "reviewed_by": 13,
            "review_remarks": "Proof did not match.",
        }
        self.query.execute.return_value = SimpleNamespace(data=[claim])
        self.set_role("Faculty", user_id=13)

        response = self.client.post(
            "/api/faculty/claims/5/decision",
            json={
                "decision": "Rejected",
                "review_remarks": "Proof did not match.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["claim"], claim)
        self.query.update.assert_called_once_with({
            "claim_status": "Rejected",
            "reviewed_by": 13,
            "review_remarks": "Proof did not match.",
        })

    def test_admin_can_make_claim_decision(self):
        claim = {
            "claim_id": 5,
            "claim_status": "Approved",
            "reviewed_by": 21,
            "review_remarks": None,
        }
        self.query.execute.return_value = SimpleNamespace(data=[claim])
        self.set_role("Admin", user_id=21)

        response = self.client.post(
            "/api/faculty/claims/5/decision",
            json={"decision": "Approved"},
        )

        self.assertEqual(response.status_code, 200)
        self.query.update.assert_called_once_with({
            "claim_status": "Approved",
            "reviewed_by": 21,
            "review_remarks": None,
        })

    def test_missing_or_invalid_decision_returns_400(self):
        self.set_role("Faculty")

        requests = (
            {"json": {}},
            {"json": {"decision": "Pending"}},
            {"json": {"decision": ["Approved"]}},
            {"data": "{", "content_type": "application/json"},
        )
        for request_args in requests:
            with self.subTest(request_args=request_args):
                response = self.client.post(
                    "/api/faculty/claims/5/decision",
                    **request_args,
                )
                self.assertEqual(response.status_code, 400)

        self.supabase.table.assert_not_called()

    def test_nonexistent_claim_returns_404(self):
        self.query.execute.side_effect = [
            SimpleNamespace(data=[]),
            SimpleNamespace(data=[]),
        ]
        self.set_role("Faculty")

        response = self.client.post(
            "/api/faculty/claims/999/decision",
            json={"decision": "Approved"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.query.execute.call_count, 2)

    def test_already_reviewed_claim_returns_409_without_overwrite(self):
        self.query.execute.side_effect = [
            SimpleNamespace(data=[]),
            SimpleNamespace(data=[{
                "claim_id": 5,
                "claim_status": "Rejected",
            }]),
        ]
        self.set_role("Faculty")

        response = self.client.post(
            "/api/faculty/claims/5/decision",
            json={"decision": "Approved"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.query.execute.call_count, 2)
        self.query.update.assert_called_once()

    def test_database_error_returns_generic_500(self):
        self.query.execute.side_effect = RuntimeError("private database detail")
        self.set_role("Faculty")

        response = self.client.post(
            "/api/faculty/claims/5/decision",
            json={"decision": "Approved"},
        )

        self.assertEqual(response.status_code, 500)
        self.assertNotIn(
            "private database detail",
            response.get_data(as_text=True),
        )


class RecordReturnRouteTests(unittest.TestCase):
    def setUp(self):
        self.rpc_query = Mock()
        self.rpc_query.execute.return_value = SimpleNamespace(data=[{
            "return_id": 4,
            "claim_id": 8,
            "item_id": 3,
            "claimant_programme": "B.Tech CS&E",
        }])

        self.supabase = Mock()
        self.supabase.rpc.return_value = self.rpc_query
        supabase_patch = patch.object(faculty_routes, "supabase", self.supabase)
        supabase_patch.start()
        self.addCleanup(supabase_patch.stop)

        app = Flask(__name__)
        app.secret_key = "test-only"
        app.register_blueprint(faculty_routes.faculty_bp)
        self.client = app.test_client()

    def set_role(self, role, user_id=1):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role

    def valid_payload(self):
        return {
            "claim_id": 8,
            "claimant_registration_no": "R12345",
            "claimant_phone": "5550100",
            "claimant_programme": "B.Tech CS&E",
            "verification_notes": "Identity checked.",
        }

    def post_return(self, **kwargs):
        return self.client.post("/api/faculty/returns", **kwargs)

    def test_faculty_success_calls_rpc_with_session_verifier_and_returns_record(self):
        self.set_role("Faculty", user_id=41)
        payload = self.valid_payload()
        payload["verified_by_faculty_id"] = 999

        response = self.post_return(json=payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json(), {
            "status": "Success",
            "returned_item": self.rpc_query.execute.return_value.data[0],
        })
        self.supabase.rpc.assert_called_once_with(
            "record_item_return",
            {
                "p_claim_id": 8,
                "p_verified_by_faculty_id": 41,
                "p_claimant_registration_no": "R12345",
                "p_claimant_phone": "5550100",
                "p_claimant_programme": "B.Tech CS&E",
                "p_verification_notes": "Identity checked.",
            },
        )
        self.rpc_query.execute.assert_called_once_with()

    def test_admin_is_authorized(self):
        self.set_role("Admin", user_id=42)

        response = self.post_return(json=self.valid_payload())

        self.assertEqual(response.status_code, 201)
        self.supabase.rpc.assert_called_once()

    def test_unauthenticated_request_returns_401(self):
        response = self.post_return(json=self.valid_payload())

        self.assertEqual(response.status_code, 401)
        self.supabase.rpc.assert_not_called()

    def test_student_request_returns_403(self):
        self.set_role("Student")

        response = self.post_return(json=self.valid_payload())

        self.assertEqual(response.status_code, 403)
        self.supabase.rpc.assert_not_called()

    def test_missing_or_malformed_json_returns_400(self):
        self.set_role("Faculty")
        invalid_requests = (
            {},
            {"data": "{", "content_type": "application/json"},
            {"json": []},
        )

        for request_args in invalid_requests:
            with self.subTest(request_args=request_args):
                response = self.post_return(**request_args)
                self.assertEqual(response.status_code, 400)

        self.supabase.rpc.assert_not_called()

    def test_missing_blank_and_overlong_required_fields_return_400(self):
        self.set_role("Faculty")
        field_limits = {
            "claimant_registration_no": 30,
            "claimant_phone": 15,
            "claimant_programme": 100,
        }
        invalid_payloads = []
        for field, max_length in field_limits.items():
            missing = self.valid_payload()
            del missing[field]
            invalid_payloads.append(missing)

            blank = self.valid_payload()
            blank[field] = "   "
            invalid_payloads.append(blank)

            too_long = self.valid_payload()
            too_long[field] = "x" * (max_length + 1)
            invalid_payloads.append(too_long)

            over_limit_with_whitespace = self.valid_payload()
            over_limit_with_whitespace[field] = "x" * max_length + " "
            invalid_payloads.append(over_limit_with_whitespace)

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.post_return(json=payload)
                self.assertEqual(response.status_code, 400)

        self.supabase.rpc.assert_not_called()

    def test_invalid_claim_id_returns_400(self):
        self.set_role("Faculty")
        for claim_id in (None, True, 0, -1, 8.5, "8"):
            with self.subTest(claim_id=claim_id):
                payload = self.valid_payload()
                payload["claim_id"] = claim_id
                response = self.post_return(json=payload)
                self.assertEqual(response.status_code, 400)

        self.supabase.rpc.assert_not_called()

    def test_invalid_or_overlong_verification_notes_returns_400(self):
        self.set_role("Faculty")
        for notes in ([], "x" * 10001):
            with self.subTest(notes_type=type(notes).__name__):
                payload = self.valid_payload()
                payload["verification_notes"] = notes
                response = self.post_return(json=payload)
                self.assertEqual(response.status_code, 400)

        self.supabase.rpc.assert_not_called()

    def test_optional_notes_can_be_omitted(self):
        self.set_role("Faculty")
        payload = self.valid_payload()
        del payload["verification_notes"]

        response = self.post_return(json=payload)

        self.assertEqual(response.status_code, 201)
        self.supabase.rpc.assert_called_once_with(
            "record_item_return",
            {
                "p_claim_id": 8,
                "p_verified_by_faculty_id": 1,
                "p_claimant_registration_no": "R12345",
                "p_claimant_phone": "5550100",
                "p_claimant_programme": "B.Tech CS&E",
                "p_verification_notes": None,
            },
        )

    def test_rpc_without_return_row_returns_generic_500(self):
        self.rpc_query.execute.return_value = SimpleNamespace(data=[])
        self.set_role("Faculty")

        response = self.post_return(json=self.valid_payload())

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.get_json()["message"],
            "Unable to record item return.",
        )

    def test_malformed_rpc_results_return_generic_500(self):
        malformed_results = (
            None,
            {},
            [],
            [{}, {}],
            [None],
            ["private database detail"],
        )
        self.set_role("Faculty")

        for data in malformed_results:
            with self.subTest(data=data):
                self.rpc_query.execute.return_value = SimpleNamespace(data=data)
                response = self.post_return(json=self.valid_payload())

                self.assertEqual(response.status_code, 500)
                self.assertEqual(
                    response.get_json()["message"],
                    "Unable to record item return.",
                )
                self.assertNotIn(
                    "private database detail",
                    response.get_data(as_text=True),
                )

    def test_known_database_errors_return_safe_responses(self):
        class RPCError(Exception):
            def __init__(self, code, message):
                super().__init__(message)
                self.code = code
                self.message = message

        cases = (
            ("P0002", "claim_not_found", 404, "Claim not found."),
            ("P0002", "item_not_found", 404, "Item not found."),
            ("P0001", "claim_not_approved", 409, "Claim is not approved."),
            ("P0001", "item_not_returnable", 409, "Item is not in a returnable status."),
            ("P0001", "return_already_recorded", 409, "A return has already been recorded for this claim or item."),
            ("23505", "duplicate return", 409, "A return has already been recorded for this claim or item."),
            ("42501", "invalid_return_verifier", 403, "The verifier is not authorized to record returns."),
        )
        self.set_role("Faculty")

        for code, detail, expected_status, expected_message in cases:
            with self.subTest(code=code, detail=detail):
                self.rpc_query.execute.side_effect = RPCError(
                    code,
                    f"{detail}: sensitive database details",
                )
                response = self.post_return(json=self.valid_payload())
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(response.get_json()["message"], expected_message)
                self.assertNotIn(
                    "sensitive database details",
                    response.get_data(as_text=True),
                )

    def test_supabase_error_payload_mapping_does_not_expose_raw_message(self):
        self.rpc_query.execute.side_effect = RuntimeError({
            "code": "P0001",
            "message": "claim_not_approved: private SQL detail",
            "details": "sensitive database detail",
        })
        self.set_role("Faculty")

        response = self.post_return(json=self.valid_payload())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["message"], "Claim is not approved.")
        self.assertNotIn("private SQL detail", response.get_data(as_text=True))
        self.assertNotIn("sensitive database detail", response.get_data(as_text=True))

    def test_unknown_or_unrecognized_database_error_returns_generic_500(self):
        class RPCError(Exception):
            def __init__(self, code, message):
                super().__init__(message)
                self.code = code
                self.message = message

        errors = (
            RPCError("P0001", "unrecognized application error with secret details"),
            RPCError("42501", "permission denied with secret details"),
            RPCError("XX000", "internal error with secret details"),
        )
        self.set_role("Faculty")

        for error in errors:
            with self.subTest(code=error.code):
                self.rpc_query.execute.side_effect = error
                response = self.post_return(json=self.valid_payload())
                self.assertEqual(response.status_code, 500)
                self.assertEqual(
                    response.get_json()["message"],
                    "Unable to record item return.",
                )
                self.assertNotIn("secret details", response.get_data(as_text=True))

    def test_invalid_details_database_error_returns_400(self):
        class RPCError(Exception):
            code = "22023"
            message = "invalid_return_details"

        self.rpc_query.execute.side_effect = RPCError()
        self.set_role("Faculty")

        response = self.post_return(json=self.valid_payload())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["message"], "Return details are invalid.")

    def test_unexpected_database_error_returns_generic_500(self):
        self.rpc_query.execute.side_effect = RuntimeError(
            "private SQL, credentials, and stack detail"
        )
        self.set_role("Faculty")

        response = self.post_return(json=self.valid_payload())

        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private SQL", response.get_data(as_text=True))
        self.assertNotIn("credentials", response.get_data(as_text=True))
        self.assertNotIn("stack detail", response.get_data(as_text=True))


class FacultyDiscoveryRouteTests(unittest.TestCase):
    def setUp(self):
        self.query = Mock()
        for method in ("select", "eq", "gte", "lte", "ilike", "order"):
            getattr(self.query, method).return_value = self.query

        self.supabase = Mock()
        self.supabase.table.return_value = self.query
        supabase_patch = patch.object(faculty_routes, "supabase", self.supabase)
        supabase_patch.start()
        self.addCleanup(supabase_patch.stop)

        app = Flask(
            __name__,
            template_folder=str(Path(__file__).resolve().parents[1] / "templates"),
        )
        app.secret_key = "test-only"
        app.register_blueprint(faculty_routes.faculty_bp)
        self.client = app.test_client()

    def set_role(self, role):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = role

    def test_portal_is_faculty_protected_and_renders(self):
        unauthorized = self.client.get("/api/faculty/portal")
        self.assertEqual(unauthorized.status_code, 401)

        self.set_role("Faculty")
        response = self.client.get("/api/faculty/portal")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Faculty &amp; Verification Portal",
            response.get_data(as_text=True),
        )
        self.supabase.table.assert_not_called()

    def test_search_applies_filters_and_returns_items(self):
        items = [{"item_id": 6, "title": "Blue backpack"}]
        self.query.execute.return_value = SimpleNamespace(data=items)
        self.set_role("Admin")

        response = self.client.get(
            "/api/faculty/items",
            query_string={
                "category_id": "2",
                "location_id": "4",
                "status": "Claimed",
                "item_type": "Found",
                "date_from": "2026-01-01",
                "date_to": "2026-02-01",
                "q": "backpack",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"status": "Success", "items": items},
        )
        self.assertEqual(
            self.query.mock_calls,
            [
                call.select(
                    "item_id, title, description, item_type, status, category_id, "
                    "location_id, date_reported, created_at, "
                    "categories(category_name), locations(location_name)"
                ),
                call.eq("category_id", 2),
                call.eq("location_id", 4),
                call.eq("status", "Claimed"),
                call.eq("item_type", "Found"),
                call.gte("date_reported", "2026-01-01"),
                call.lte("date_reported", "2026-02-01"),
                call.ilike("title", "%backpack%"),
                call.order("date_reported", desc=True),
                call.execute(),
            ],
        )

    def test_search_rejects_invalid_filter_values_without_database_access(self):
        self.set_role("Faculty")
        invalid_queries = (
            {"category_id": "0"},
            {"location_id": "not-an-id"},
            {"status": "Unknown"},
            {"item_type": "Missing"},
            {"date_from": "2026-02-30"},
            {"date_from": "2026-02-02", "date_to": "2026-02-01"},
            {"q": "x" * 101},
        )

        for query_string in invalid_queries:
            with self.subTest(query_string=query_string):
                response = self.client.get(
                    "/api/faculty/items",
                    query_string=query_string,
                )
                self.assertEqual(response.status_code, 400)

        self.supabase.table.assert_not_called()

    def test_search_and_return_history_reject_unauthorized_users(self):
        for path in ("/api/faculty/items", "/api/faculty/returns"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)
        self.set_role("Student")
        self.assertEqual(self.client.get("/api/faculty/items").status_code, 403)
        self.assertEqual(self.client.get("/api/faculty/returns").status_code, 403)
        self.supabase.table.assert_not_called()

    def test_item_details_include_approved_claims(self):
        item = {"item_id": 7, "title": "Blue backpack"}
        claims = [{"claim_id": 9, "claim_status": "Approved"}]
        item_query = Mock()
        item_query.select.return_value = item_query
        item_query.eq.return_value = item_query
        item_query.execute.return_value = SimpleNamespace(data=[item])
        claims_query = Mock()
        claims_query.select.return_value = claims_query
        claims_query.eq.return_value = claims_query
        claims_query.execute.return_value = SimpleNamespace(data=claims)
        self.supabase.table.side_effect = [item_query, claims_query]
        self.set_role("Faculty")

        response = self.client.get("/api/faculty/items/7")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "status": "Success",
            "item": item,
            "approved_claims": claims,
        })
        self.assertEqual(
            self.supabase.table.call_args_list,
            [call("items"), call("claims")],
        )
        claims_query.eq.assert_any_call("claim_status", "Approved")

    def test_item_details_returns_404_without_querying_claims_when_missing(self):
        item_query = Mock()
        item_query.select.return_value = item_query
        item_query.eq.return_value = item_query
        item_query.execute.return_value = SimpleNamespace(data=[])
        self.supabase.table.return_value = item_query
        self.set_role("Faculty")

        response = self.client.get("/api/faculty/items/999")

        self.assertEqual(response.status_code, 404)
        self.supabase.table.assert_called_once_with("items")

    def test_return_history_returns_database_records_in_order(self):
        records = [{"return_id": 3, "claimant_phone": "5550100"}]
        self.query.execute.return_value = SimpleNamespace(data=records)
        self.set_role("Faculty")

        response = self.client.get("/api/faculty/returns")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "status": "Success",
            "returns": records,
        })
        self.assertEqual(
            self.query.mock_calls,
            [
                call.select("*"),
                call.order("return_date", desc=True),
                call.execute(),
            ],
        )

    def test_search_and_history_database_errors_are_generic(self):
        self.query.execute.side_effect = RuntimeError(
            "private database detail and credentials"
        )
        self.set_role("Faculty")

        for path in ("/api/faculty/items", "/api/faculty/returns"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn(
                    "private database detail",
                    response.get_data(as_text=True),
                )
                self.assertNotIn(
                    "credentials",
                    response.get_data(as_text=True),
                )

    def test_search_options_returns_categories_and_locations(self):
        category_query = Mock()
        category_query.select.return_value = category_query
        category_query.order.return_value = category_query
        category_query.execute.return_value = SimpleNamespace(
            data=[{"category_id": 2, "category_name": "Electronics"}]
        )
        location_query = Mock()
        location_query.select.return_value = location_query
        location_query.order.return_value = location_query
        location_query.execute.return_value = SimpleNamespace(
            data=[{"location_id": 4, "location_name": "Library"}]
        )
        self.supabase.table.side_effect = [category_query, location_query]
        self.set_role("Faculty")

        response = self.client.get("/api/faculty/search-options")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "status": "Success",
            "categories": [{"category_id": 2, "category_name": "Electronics"}],
            "locations": [{"location_id": 4, "location_name": "Library"}],
        })


if __name__ == "__main__":
    unittest.main()
