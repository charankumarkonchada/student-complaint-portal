import os
import sys
import time
import unittest
import io

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

venv_site = os.path.join(BASE_DIR, ".venv", "lib", "python3.13", "site-packages")
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.append(venv_site)

from werkzeug.security import generate_password_hash

import config

# Force isolated SQLite test database
TEST_DB_PATH = os.path.join(BASE_DIR, "test_e2e.db")
config.DATABASE_URL = ""
config.DATABASE = TEST_DB_PATH
config.SECRET_KEY = "test-e2e-secret-key-456"

from app import create_app
from database.db import get_db_connection
from database.queries import init_database
from services.common_issue_service import (
    create_common_issue,
    update_common_issue_once,
    associate_complaint_to_common_issue,
    get_common_issue_with_stats,
    get_common_issue_complaints,
)


class TestIntelliHostelE2EWorkflows(unittest.TestCase):
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
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

    # =========================================================================
    # PART 4: STUDENT WORKFLOW TEST
    # =========================================================================
    def test_01_student_registration_and_validation(self):
        """Test student registration with validations (college email, ID format, password match)."""
        # Mismatched email and ID
        res = self.client.post("/register", data={
            "name": "Invalid Student",
            "id_no": "O210001",
            "email": "wrong@rguktong.ac.in",
            "phone": "9876543210",
            "hostel": "Hostel Block A",
            "room": "101",
            "password": "password123",
            "confirm_password": "password123"
        }, follow_redirects=True)
        self.assertIn(b"ID Number and college email do not match", res.data)

        # Successful registration Student 1
        res = self.client.post("/register", data={
            "name": "Student Alpha",
            "id_no": "O210001",
            "email": "o210001@rguktong.ac.in",
            "phone": "9876543210",
            "hostel": "Hostel Block A",
            "room": "101",
            "password": "password123",
            "confirm_password": "password123"
        }, follow_redirects=True)
        self.assertIn(b"Registration Successful", res.data)

        # Successful registration Student 2
        res = self.client.post("/register", data={
            "name": "Student Beta",
            "id_no": "O210002",
            "email": "o210002@rguktong.ac.in",
            "phone": "9876543211",
            "hostel": "Hostel Block A",
            "room": "102",
            "password": "password123",
            "confirm_password": "password123"
        }, follow_redirects=True)
        self.assertIn(b"Registration Successful", res.data)

        # Duplicate registration rejection
        res = self.client.post("/register", data={
            "name": "Duplicate Alpha",
            "id_no": "O210001",
            "email": "o210001@rguktong.ac.in",
            "phone": "9876543210",
            "hostel": "Hostel Block A",
            "room": "101",
            "password": "password123",
            "confirm_password": "password123"
        }, follow_redirects=True)
        self.assertIn(b"ID Number Already Exists", res.data)

    def test_02_student_login_and_dashboard(self):
        """Test student login and accessing dashboard."""
        # Wrong password
        res = self.client.post("/login", data={
            "id_no": "O210001",
            "password": "wrongpassword"
        }, follow_redirects=True)
        self.assertIn(b"Invalid ID Number or Password", res.data)

        # Correct login
        res = self.client.post("/login", data={
            "id_no": "O210001",
            "password": "password123"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Student Alpha", res.data)
        self.assertIn(b"Dashboard", res.data)

    def test_03_student_submit_complaint_and_view(self):
        """Test complaint submission (with and without attachment) and view complaint."""
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["student_name"] = "Student Alpha"
            sess["id_no"] = "O210001"
            sess["email"] = "o210001@rguktong.ac.in"
            sess["hostel"] = "Hostel Block A"
            sess["room_no"] = "101"

        # Submit Complaint 1 without image
        res = self.client.post("/add_complaint", data={
            "category": "Electrical",
            "priority": "High",
            "title": "Ceiling fan motor burning smell",
            "description": "The ceiling fan in room 101 makes abnormal sparks and emits a burning smell."
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Ceiling fan motor burning smell", res.data)
        self.assertIn(b"Electrical", res.data)

        # Submit Complaint 2 with mock image attachment
        mock_image = (io.BytesIO(b"fake image bytes"), "evidence.jpg")
        res = self.client.post("/add_complaint", data={
            "category": "Plumbing",
            "priority": "Medium",
            "title": "Leaking washroom tap",
            "description": "Washroom tap continuously dripping water on second floor.",
            "image": mock_image
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Leaking washroom tap", res.data)

        # View complaint history
        res = self.client.get("/complaint_history")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Ceiling fan motor burning smell", res.data)
        self.assertIn(b"Leaking washroom tap", res.data)

    def test_04_activity_page_robustness(self):
        """CRITICAL: Ensure /activity NEVER returns 500 even with complex datetime types and history entries."""
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["student_name"] = "Student Alpha"
            sess["id_no"] = "O210001"
            sess["email"] = "o210001@rguktong.ac.in"
            sess["hostel"] = "Hostel Block A"
            sess["room_no"] = "101"

        res = self.client.get("/activity")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Recent Activity", res.data)
        self.assertIn(b"Ceiling fan motor burning smell", res.data)

    def test_05_student_profile_and_password_change(self):
        """Test student profile view/edit and password change."""
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["student_name"] = "Student Alpha"
            sess["id_no"] = "O210001"
            sess["email"] = "o210001@rguktong.ac.in"
            sess["hostel"] = "Hostel Block A"
            sess["room_no"] = "101"

        # View Profile
        res = self.client.get("/profile")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Student Alpha", res.data)

        # Update Profile
        res = self.client.post("/profile", data={
            "phone": "9998887776",
            "hostel": "Hostel Block A",
            "room_no": "105"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Change Password - wrong old password
        res = self.client.post("/change_password", data={
            "old_password": "wrongoldpassword",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123"
        }, follow_redirects=True)
        self.assertIn(b"Current password is incorrect", res.data)

        # Change Password - success
        res = self.client.post("/change_password", data={
            "old_password": "password123",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123"
        }, follow_redirects=True)
        self.assertIn(b"Password Updated Successfully", res.data)

        # Logout
        res = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Logged Out Successfully", res.data)

    # =========================================================================
    # PART 5: ADMIN WORKFLOW & COMMON ISSUE BULK PROPAGATION
    # =========================================================================
    def test_06_admin_login_and_dashboard(self):
        """Test admin login and access to dashboard & complaints."""
        # Incorrect admin credentials
        res = self.client.post("/admin_login", data={
            "username": config.ADMIN_USERNAME,
            "password": "wrongadminpassword"
        }, follow_redirects=True)
        self.assertIn(b"Invalid Username or Password", res.data)

        # Correct admin credentials
        res = self.client.post("/admin_login", data={
            "username": config.ADMIN_USERNAME,
            "password": config.ADMIN_PASSWORD
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Admin Dashboard", res.data)

        # Manage Complaints list
        res = self.client.get("/manage_complaints")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Ceiling fan motor burning smell", res.data)

    def test_07_single_complaint_status_update(self):
        """Test individual complaint status update by admin."""
        with self.client.session_transaction() as sess:
            sess["admin"] = config.ADMIN_USERNAME

        res = self.client.post("/update_status/1", data={
            "status": "In Progress",
            "assigned_to": "Electrician Suresh",
            "remarks": "Inspected, spare motor requested from store."
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Complaint Updated Successfully", res.data)

        # Verify notification was generated for student 1
        conn = get_db_connection()
        notif = conn.execute("SELECT * FROM notifications WHERE student_id=1 ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        self.assertIsNotNone(notif)
        self.assertIn("In Progress", notif["message"])

    def test_08_common_issue_lifecycle_and_single_action_update(self):
        """Test Common Issue creation, multi-complaint linking, single-action bulk update, and notification."""
        conn = get_db_connection()
        # Seed 3 complaints in Hostel Block B for water outage
        for i in range(10, 13):
            # student
            conn.execute(
                "INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (i, f"Hostel B Student {i}", f"O2100{i}", f"o2100{i}@rguktong.ac.in", "9000000000", "Hostel Block B", f"30{i}", generate_password_hash("pass"))
            )
            # complaint
            conn.execute(
                """
                INSERT INTO complaints (id, student_id, category, title, description, priority, status)
                VALUES (?, ?, 'Plumbing', 'No water supply in Block B 3rd floor', 'No running water since morning', 'High', 'Pending')
                """,
                (i, i)
            )
        conn.commit()

        # Admin creates Common Issue
        with self.client.session_transaction() as sess:
            sess["admin"] = config.ADMIN_USERNAME

        res = self.client.post("/admin/common_issue/create", data={
            "title": "Hostel Block B Water Supply Interruption",
            "category": "Plumbing",
            "hostel": "Hostel Block B",
            "location_details": "3rd Floor overhead tank valve",
            "description": "Main water booster valve jammed.",
            "priority": "High",
            "assigned_to": "Chief Plumber Ramesh",
            "admin_remarks": "Technician dispatched to overhead tank.",
            "complaint_ids": ["10", "11", "12"]
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Inspect Common Issue view
        issue_id = 1
        res = self.client.get(f"/admin/common_issue/{issue_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Hostel Block B Water Supply Interruption", res.data)
        self.assertIn(b"Hostel B Student 10", res.data)

        # Execute Single-Action Update to "Resolved"
        res = self.client.post(f"/admin/common_issue/{issue_id}/update", data={
            "status": "Resolved",
            "remarks": "Booster valve replaced. Water flow tested and verified on all floors.",
            "assigned_to": "Chief Plumber Ramesh"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Successfully synchronized 3 associated student complaint(s)", res.data)

        # Verify all 3 complaints updated to 'Resolved' in single atomic transaction
        complaints = conn.execute("SELECT id, status, remarks FROM complaints WHERE common_issue_id=?", (issue_id,)).fetchall()
        self.assertEqual(len(complaints), 3)
        for c in complaints:
            self.assertEqual(c["status"], "Resolved")
            self.assertIn("Booster valve replaced", c["remarks"])

        # Verify broadcast notification exists
        broadcast_notif = conn.execute(
            "SELECT * FROM common_issue_notifications WHERE common_issue_id=?",
            (issue_id,)
        ).fetchone()
        self.assertIsNotNone(broadcast_notif)
        self.assertIn("Resolved", broadcast_notif["message"])
        conn.close()

    # =========================================================================
    # PART 7: CROSS-STUDENT PRIVACY VERIFICATION
    # =========================================================================
    def test_09_cross_student_privacy(self):
        """Verify that student view never displays peer student names, rooms, or IDs."""
        # Student 10 logs in
        with self.client.session_transaction() as sess:
            sess["student_id"] = 10
            sess["student_name"] = "Hostel B Student 10"
            sess["id_no"] = "O210010"
            sess["email"] = "o210010@rguktong.ac.in"
            sess["hostel"] = "Hostel Block B"
            sess["room_no"] = "3010"

        # View complaint 10 (linked to Common Issue #1)
        res = self.client.get("/complaint/10")
        self.assertEqual(res.status_code, 200)
        content = res.data.decode("utf-8")

        # Verify Common Issue master info is shown
        self.assertIn("Hostel Block B Water Supply Interruption", content)
        self.assertIn("Resolved", content)
        self.assertIn("Booster valve replaced", content)

        # CRITICAL PRIVACY CHECK: Peer students (Student 11 and Student 12) MUST NOT be leaked
        self.assertNotIn("Hostel B Student 11", content)
        self.assertNotIn("Hostel B Student 12", content)
        self.assertNotIn("O210011", content)
        self.assertNotIn("O210012", content)
        self.assertNotIn("3011", content)
        self.assertNotIn("3012", content)

        # Direct authorization test: Student 10 attempts to view Student 11's private complaint
        res = self.client.get("/complaint/11", follow_redirects=True)
        # Should be blocked / redirected
        self.assertIn(b"Complaint Not Found", res.data)

    # =========================================================================
    # PART 9 & 10: NOTIFICATIONS READ STATUS & ACTIVITY
    # =========================================================================
    def test_10_notifications_and_read_isolation(self):
        """Test that per-student read status is completely isolated for broadcast notifications."""
        # Student 10 checks notifications
        with self.client.session_transaction() as sess:
            sess["student_id"] = 10
            sess["student_name"] = "Hostel B Student 10"

        res = self.client.get("/notifications")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Water Supply Interruption", res.data)

        # Student 10 marks all notifications as read
        res = self.client.post("/notifications/read_all", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify Student 10 now has 0 unread notifications
        from database.queries import unread_count
        from flask import session as flask_sess
        with self.app.test_request_context("/"):
            flask_sess["student_id"] = 10
            self.assertEqual(unread_count(), 0)

        # Verify Student 11 STILL has unread notification (not affected by Student 10)
        with self.app.test_request_context("/"):
            flask_sess["student_id"] = 11
            self.assertGreater(unread_count(), 0)

    # =========================================================================
    # PART 16: SCALABILITY BENCHMARK
    # =========================================================================
    def test_11_scalability_benchmark(self):
        """Benchmark single-action common issue update at 10, 100, 1,000, and 10,000 complaints."""
        conn = get_db_connection()

        # Create a scalability test common issue
        ci_id = create_common_issue(
            title="Campus-wide High Speed Wi-Fi Router Firmware Upgrade",
            category="Internet / Wi-Fi",
            hostel="All Hostels",
            location_details="Hostel Wi-Fi Access Points",
            description="Mass access point maintenance.",
            priority="High",
            assigned_to="Network Operations Center",
            conn=conn
        )

        test_scales = [10, 100, 1000, 10000]
        timings = {}

        current_total = 0
        for scale in test_scales:
            needed = scale - current_total
            if needed > 0:
                complaint_records = []
                base_id = 100000 + current_total
                for j in range(needed):
                    cid = base_id + j
                    complaint_records.append((
                        cid, 1, "Internet / Wi-Fi",
                        f"Wi-Fi connection dropped #{cid}",
                        "Unable to connect to hostel SSID",
                        "Medium", "Pending", ci_id
                    ))

                conn.executemany(
                    """
                    INSERT INTO complaints (id, student_id, category, title, description, priority, status, common_issue_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    complaint_records
                )
                conn.commit()
                current_total = scale

            # Measure single-action update time
            start = time.perf_counter()
            affected = update_common_issue_once(
                common_issue_id=ci_id,
                status=f"In Progress - Scale {scale}",
                remarks=f"Firmware rolling upgrade phase at scale {scale}",
                assigned_to="NOC Engineering",
                updated_by="System Benchmark",
                conn=conn
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            timings[scale] = (elapsed_ms, affected)

            self.assertEqual(affected, scale)
            # Check execution time: sub-second for all scales
            self.assertLess(elapsed_ms, 1500.0, f"Scale {scale} took {elapsed_ms:.2f}ms (>1500ms)")

        conn.close()

        print("\n--- SCALABILITY BENCHMARK RESULTS ---")
        for scale, (ms, aff) in timings.items():
            print(f"  Scale {scale:>5} complaints: {ms:>7.2f} ms | Synchronized {aff} rows")
        print("------------------------------------\n")


if __name__ == "__main__":
    unittest.main()
