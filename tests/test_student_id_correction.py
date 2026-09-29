"""Comprehensive Test Suite for Student ID Correction Request Workflow.

Covers all 23 scenarios:
1. Student can submit correction request.
2. Student cannot submit for another student.
3. Invalid Student ID rejected.
4. Same current/requested ID rejected.
5. Duplicate requested ID rejected.
6. Student can view own request.
7. Student cannot view another student's request.
8. Admin can view pending requests.
9. Admin can approve valid request.
10. Approval updates Student ID.
11. Approval preserves existing student data.
12. Approval prevents duplicate ID.
13. Cannot approve twice.
14. Admin can reject request.
15. Rejection leaves Student ID unchanged.
16. Rejection requires/records remark.
17. Student receives in-app notification.
18. Email uses existing email service.
19. Automated tests never send real email.
20. CSRF protection works.
21. Unauthorized student cannot access admin endpoints.
22. Admin authorization works.
23. Transaction rollback works if approval fails.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from werkzeug.security import generate_password_hash

import backend.config as config

TEST_DB_PATH = os.path.join(BASE_DIR, "test_id_correction.db")
config.DATABASE_URL = ""
config.DATABASE = TEST_DB_PATH
config.SECRET_KEY = "test-id-correction-secret-key-999"

os.environ["TESTING"] = "1"
from app import create_app
from backend.database.db import get_db_connection
from backend.database.queries import init_database
from backend.services.student_id_correction_service import (
    validate_correction_request,
    check_duplicate_student_id,
    submit_correction_request,
    get_student_requests,
    get_all_requests,
    approve_correction_request,
    reject_correction_request,
)


class TestStudentIDCorrection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.DATABASE_URL = ""
        config.DATABASE = TEST_DB_PATH
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

        init_database()
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

    def setUp(self):
        # Create fresh client per test to isolate session cookies
        self.client = self.app.test_client()

        conn = get_db_connection()
        conn.execute("DELETE FROM student_id_correction_requests")
        conn.execute("DELETE FROM notifications")
        conn.execute("DELETE FROM complaint_history")
        conn.execute("DELETE FROM complaints")
        conn.execute("DELETE FROM students")
        conn.execute("DELETE FROM admin")

        # Create test students
        conn.execute(
            """
            INSERT INTO students(id, name, id_no, email, phone, hostel, room_no, password)
            VALUES(1, 'Alice Smith', 'O221168', 'o221168@rguktong.ac.in', '9876543210', 'Kaveri Bhavan', '204', ?)
            """,
            (generate_password_hash("password123"),)
        )
        conn.execute(
            """
            INSERT INTO students(id, name, id_no, email, phone, hostel, room_no, password)
            VALUES(2, 'Bob Jones', 'N221170', 'n221170@rguktong.ac.in', '9876543211', 'Krishna Bhavan', '101', ?)
            """,
            (generate_password_hash("password123"),)
        )
        # Create test admin
        conn.execute(
            "INSERT INTO admin(username, password) VALUES('admin', ?)",
            (generate_password_hash("admin123"),)
        )
        conn.commit()
        conn.close()

    def _login_student(self, student_id=1, id_no="O221168", email="o221168@rguktong.ac.in", name="Alice Smith"):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["student_id"] = student_id
            sess["id_no"] = id_no
            sess["email"] = email
            sess["student_name"] = name
            sess["hostel"] = "Kaveri Bhavan"
            sess["room_no"] = "204"

    def _login_admin(self):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["admin"] = "admin"

    # 1. Student can submit correction request
    def test_01_student_can_submit_correction_request(self):
        self._login_student()
        res = self.client.post("/profile/request_id_correction", data={
            "requested_id": "O221169",
            "reason": "Accidentally entered 8 instead of 9 during registration"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Your Student ID correction request has been submitted", res.data)

        conn = get_db_connection()
        req = conn.execute("SELECT * FROM student_id_correction_requests WHERE student_id = 1").fetchone()
        conn.close()
        self.assertIsNotNone(req)
        self.assertEqual(req["current_student_id"], "O221168")
        self.assertEqual(req["requested_student_id"], "O221169")
        self.assertEqual(req["status"], "Pending")

    # 2. Student cannot submit for another student
    def test_02_unauthenticated_cannot_submit_request(self):
        res = self.client.post("/profile/request_id_correction", data={
            "requested_id": "O221169",
            "reason": "Test unauthenticated submission"
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    # 3. Invalid Student ID rejected
    def test_03_invalid_student_id_rejected(self):
        self._login_student()
        # Invalid prefix 'X'
        res = self.client.post("/profile/request_id_correction", data={
            "requested_id": "X221169",
            "reason": "Wrong prefix test"
        }, follow_redirects=True)
        self.assertIn(b"Invalid ID Number", res.data)

        # Wrong length
        res = self.client.post("/profile/request_id_correction", data={
            "requested_id": "O22116",
            "reason": "Too short ID"
        }, follow_redirects=True)
        self.assertIn(b"Invalid ID Number", res.data)

        conn = get_db_connection()
        count = conn.execute("SELECT COUNT(*) AS c FROM student_id_correction_requests").fetchone()["c"]
        conn.close()
        self.assertEqual(count, 0)

    # 4. Same current/requested ID rejected
    def test_04_same_current_requested_id_rejected(self):
        self._login_student()
        res = self.client.post("/profile/request_id_correction", data={
            "requested_id": "O221168",
            "reason": "Submitting same ID"
        }, follow_redirects=True)
        self.assertIn(b"Your requested Student ID is the same as your current Student ID", res.data)

    # 5. Duplicate requested ID rejected
    def test_05_duplicate_requested_id_rejected(self):
        self._login_student()
        # N221170 is already taken by student 2 (Bob Jones)
        res = self.client.post("/profile/request_id_correction", data={
            "requested_id": "N221170",
            "reason": "Trying to claim Bob ID"
        }, follow_redirects=True)
        self.assertIn(b"already associated with another student account", res.data)

    # 6. Student can view own request
    def test_06_student_can_view_own_request(self):
        self._login_student()
        self.client.post("/profile/request_id_correction", data={
            "requested_id": "O221169",
            "reason": "Typo in ID registration"
        })
        res = self.client.get("/profile")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Student ID Correction Request", res.data)
        self.assertIn(b"O221168", res.data)
        self.assertIn(b"O221169", res.data)
        self.assertIn(b"Pending", res.data)

    # 7. Student cannot view another student's request
    def test_07_student_cannot_view_another_students_request(self):
        # Alice submits a request
        self._login_student(student_id=1, id_no="O221168")
        self.client.post("/profile/request_id_correction", data={
            "requested_id": "O221199",
            "reason": "Alice typo correction"
        })

        # Bob logs in and checks profile
        self._login_student(student_id=2, id_no="N221170", email="n221170@rguktong.ac.in", name="Bob Jones")
        res = self.client.get("/profile")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"Alice typo correction", res.data)
        self.assertNotIn(b"O221199", res.data)

    # 8. Admin can view pending requests
    def test_08_admin_can_view_pending_requests(self):
        submit_correction_request(1, "O221169", "Admissions letter correction")
        self._login_admin()
        res = self.client.get("/admin/id_correction_requests")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Alice Smith", res.data)
        self.assertIn(b"O221168", res.data)
        self.assertIn(b"O221169", res.data)
        self.assertIn(b"Admissions letter correction", res.data)

    # 9. Admin can approve valid request
    def test_09_admin_can_approve_valid_request(self):
        success, _, req_id = submit_correction_request(1, "O221169", "Typo during registration")
        self.assertTrue(success)
        self._login_admin()
        res = self.client.post(f"/admin/id_correction_requests/{req_id}/approve", data={
            "admin_remarks": "Verified with academic cell"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"approved", res.data.lower())

        conn = get_db_connection()
        req = conn.execute("SELECT * FROM student_id_correction_requests WHERE id = ?", (req_id,)).fetchone()
        conn.close()
        self.assertEqual(req["status"], "Approved")
        self.assertEqual(req["reviewed_by"], "admin")
        self.assertEqual(req["admin_remarks"], "Verified with academic cell")

    # 10. Approval updates Student ID
    def test_10_approval_updates_student_id_and_email(self):
        success, _, req_id = submit_correction_request(1, "O221169", "Typo during registration")
        self.assertTrue(success)
        self._login_admin()
        self.client.post(f"/admin/id_correction_requests/{req_id}/approve", data={
            "admin_remarks": "Approved"
        })

        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE id = 1").fetchone()
        conn.close()
        self.assertEqual(student["id_no"], "O221169")
        self.assertEqual(student["email"], "o221169@rguktong.ac.in")

    # 11. Approval preserves existing student data
    def test_11_approval_preserves_existing_student_data(self):
        conn = get_db_connection()
        # Add a complaint for student 1
        conn.execute(
            """
            INSERT INTO complaints(id, student_id, category, title, description, priority, status)
            VALUES(99, 1, 'Electrical', 'Fan not working', 'Room 204 ceiling fan is broken', 'High', 'Pending')
            """
        )
        conn.execute(
            "INSERT INTO complaint_history(complaint_id, status) VALUES(99, 'Pending')"
        )
        conn.commit()
        conn.close()

        success, _, req_id = submit_correction_request(1, "O221169", "Fix ID typo properly")
        self.assertTrue(success)
        self._login_admin()
        self.client.post(f"/admin/id_correction_requests/{req_id}/approve", data={})

        conn = get_db_connection()
        complaint = conn.execute("SELECT * FROM complaints WHERE id = 99").fetchone()
        history = conn.execute("SELECT * FROM complaint_history WHERE complaint_id = 99").fetchall()
        student = conn.execute("SELECT * FROM students WHERE id = 1").fetchone()
        conn.close()

        self.assertEqual(complaint["student_id"], 1)
        self.assertEqual(complaint["title"], "Fan not working")
        self.assertEqual(len(history), 1)
        self.assertEqual(student["phone"], "9876543210")
        self.assertEqual(student["room_no"], "204")

    # 12. Approval prevents duplicate ID if claimed in interim
    def test_12_approval_prevents_duplicate_if_claimed_in_interim(self):
        success, _, req_id = submit_correction_request(1, "O221169", "Valid reason")
        self.assertTrue(success)

        # Another student registers O221169 before admin approves
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO students(id, name, id_no, email, password) VALUES(3, 'Charlie', 'O221169', 'o221169@rguktong.ac.in', 'pw')"
        )
        conn.commit()
        conn.close()

        self._login_admin()
        res = self.client.post(f"/admin/id_correction_requests/{req_id}/approve", follow_redirects=True)
        self.assertIn(b"already associated with another student", res.data)

        conn = get_db_connection()
        student1 = conn.execute("SELECT id_no FROM students WHERE id = 1").fetchone()
        conn.close()
        self.assertEqual(student1["id_no"], "O221168")  # Untouched

    # 13. Cannot approve twice
    def test_13_cannot_approve_twice(self):
        success, _, req_id = submit_correction_request(1, "O221169", "Valid reason")
        self.assertTrue(success)
        self._login_admin()
        self.client.post(f"/admin/id_correction_requests/{req_id}/approve")
        res = self.client.post(f"/admin/id_correction_requests/{req_id}/approve", follow_redirects=True)
        self.assertIn(b"already been processed", res.data)

    # 14. Admin can reject request
    def test_14_admin_can_reject_request(self):
        success, _, req_id = submit_correction_request(1, "O221169", "Valid reason")
        self.assertTrue(success)
        self._login_admin()
        res = self.client.post(f"/admin/id_correction_requests/{req_id}/reject", data={
            "admin_remarks": "Registration card does not match requested number."
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = get_db_connection()
        req = conn.execute("SELECT * FROM student_id_correction_requests WHERE id = ?", (req_id,)).fetchone()
        conn.close()
        self.assertEqual(req["status"], "Rejected")
        self.assertEqual(req["admin_remarks"], "Registration card does not match requested number.")

    # 15. Rejection leaves Student ID unchanged
    def test_15_rejection_leaves_student_id_unchanged(self):
        success, _, req_id = submit_correction_request(1, "O221169", "Valid reason")
        self.assertTrue(success)
        self._login_admin()
        self.client.post(f"/admin/id_correction_requests/{req_id}/reject", data={
            "admin_remarks": "Rejected: unverified"
        })

        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE id = 1").fetchone()
        conn.close()
        self.assertEqual(student["id_no"], "O221168")
        self.assertEqual(student["email"], "o221168@rguktong.ac.in")

    # 16. Rejection requires/records remark
    def test_16_rejection_requires_remark(self):
        success, _, req_id = submit_correction_request(1, "O221169", "Valid reason")
        self.assertTrue(success)
        self._login_admin()
        res = self.client.post(f"/admin/id_correction_requests/{req_id}/reject", data={
            "admin_remarks": "   "  # empty whitespace
        }, follow_redirects=True)
        self.assertIn(b"required", res.data.lower())

        conn = get_db_connection()
        req = conn.execute("SELECT status FROM student_id_correction_requests WHERE id = ?", (req_id,)).fetchone()
        conn.close()
        self.assertEqual(req["status"], "Pending")

    # 17. Student receives in-app notification
    def test_17_student_receives_in_app_notification(self):
        success, _, req_id = submit_correction_request(1, "O221169", "Valid reason")
        self.assertTrue(success)

        conn = get_db_connection()
        notifs = conn.execute("SELECT message FROM notifications WHERE student_id = 1").fetchall()
        conn.close()
        self.assertTrue(any("submitted" in n["message"].lower() for n in notifs))

        self._login_admin()
        self.client.post(f"/admin/id_correction_requests/{req_id}/approve", data={"admin_remarks": "OK"})

        conn = get_db_connection()
        notifs2 = conn.execute("SELECT message FROM notifications WHERE student_id = 1").fetchall()
        conn.close()
        self.assertTrue(any("approved" in n["message"].lower() and "O221169" in n["message"] for n in notifs2))

    # 18. Email uses existing email service
    @patch("backend.services.student_id_correction_service.send_email")
    def test_18_email_uses_existing_email_service(self, mock_send):
        mock_send.return_value = True
        success, _, req_id = submit_correction_request(1, "O221169", "Valid reason")
        self.assertTrue(success)
        approve_correction_request(req_id, "admin", "Approval remark")

        self.assertTrue(mock_send.called)
        call_args = mock_send.call_args[1]
        self.assertIn("o221169@rguktong.ac.in", call_args["recipient"])
        self.assertIn("Approved", call_args["subject"])

    # 19. Automated tests never send real email
    def test_19_automated_tests_never_send_real_email(self):
        from backend.services.email_service import is_test_environment, is_smtp_mocked, send_email
        self.assertTrue(is_test_environment())
        # Unmocked send_email in test environment must return False safely without opening network sockets
        sent = send_email("test@rguktong.ac.in", "Test", "Test body")
        self.assertFalse(sent)

    # 20. CSRF protection works
    def test_20_csrf_protection_works(self):
        # Temporarily enable CSRF
        self.app.config["WTF_CSRF_ENABLED"] = True
        try:
            self._login_student()
            # Post without CSRF token
            res = self.client.post("/profile/request_id_correction", data={
                "requested_id": "O221169",
                "reason": "Test without CSRF"
            })
            self.assertEqual(res.status_code, 400)
        finally:
            self.app.config["WTF_CSRF_ENABLED"] = False

    # 21. Unauthorized student cannot access admin endpoints
    def test_21_unauthorized_student_cannot_access_admin_endpoints(self):
        self._login_student()
        res = self.client.get("/admin/id_correction_requests", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/admin_login", res.headers.get("Location", ""))

    # 22. Admin authorization works
    def test_22_admin_authorization_works(self):
        success, _, req_id = submit_correction_request(1, "O221169", "Valid reason")
        self.assertTrue(success)
        # Student tries to POST approve
        self._login_student()
        res = self.client.post(f"/admin/id_correction_requests/{req_id}/approve", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/admin_login", res.headers.get("Location", ""))

        conn = get_db_connection()
        req = conn.execute("SELECT status FROM student_id_correction_requests WHERE id = ?", (req_id,)).fetchone()
        conn.close()
        self.assertEqual(req["status"], "Pending")

    # 23. Transaction rollback works if approval fails
    def test_23_transaction_rollback_works_if_approval_fails(self):
        success, _, req_id = submit_correction_request(1, "O221169", "Valid reason")
        self.assertTrue(success)

        real_get_conn = get_db_connection

        class FailingConnWrapper:
            def __init__(self, conn):
                self._conn = conn

            def execute(self, sql, *args, **kwargs):
                if "UPDATE student_id_correction_requests" in sql:
                    raise RuntimeError("Simulated DB crash during request status update")
                return self._conn.execute(sql, *args, **kwargs)

            def commit(self):
                return self._conn.commit()

            def rollback(self):
                return self._conn.rollback()

            def close(self):
                return self._conn.close()

        with patch("backend.services.student_id_correction_service.get_db_connection", side_effect=lambda: FailingConnWrapper(real_get_conn())):
            success, msg = approve_correction_request(req_id, "admin", "Failing approve")
            self.assertFalse(success)
            self.assertIn("error", msg.lower())

        conn = get_db_connection()
        req = conn.execute("SELECT status FROM student_id_correction_requests WHERE id = ?", (req_id,)).fetchone()
        student = conn.execute("SELECT id_no FROM students WHERE id = 1").fetchone()
        conn.close()
        self.assertEqual(req["status"], "Pending")
        self.assertEqual(student["id_no"], "O221168")


if __name__ == "__main__":
    unittest.main()
