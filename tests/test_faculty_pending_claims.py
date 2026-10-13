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
                call.select("*"),
                call.eq("claim_status", "Pending"),
                call.execute(),
                call.select("*"),
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


if __name__ == "__main__":
    unittest.main()
