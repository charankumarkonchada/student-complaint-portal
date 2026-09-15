import os
import sys
import time
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

venv_site = os.path.join(BASE_DIR, ".venv", "lib", "python3.13", "site-packages")
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.append(venv_site)

from werkzeug.security import generate_password_hash

import config

# Force isolated SQLite test database
TEST_DB_PATH = os.path.join(BASE_DIR, "test_database.db")
config.DATABASE_URL = ""
config.DATABASE = TEST_DB_PATH
config.SECRET_KEY = "test-secret-key-123"

from app import create_app
from database.db import get_db_connection
from database.queries import init_database
from services.common_issue_service import (
    create_common_issue,
    find_matching_common_issue,
    update_common_issue_once,
    get_common_issue_with_stats,
    get_common_issue_complaints,
    unlink_complaint_from_common_issue,
    associate_complaint_to_common_issue,
)

class TestCommonIssueScalability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.DATABASE_URL = ""
        config.DATABASE = TEST_DB_PATH
        # Remove old test DB if present
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass
        
        # Initialize test database
        init_database()
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

        # Seed primary test students
        conn = get_db_connection()
        # Student in Hostel Block A
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (1, 'Alice Student', 'O200001', 'o200001@rguktong.ac.in', '9876543210', 'Hostel Block A', '201', ?)
            """,
            (generate_password_hash("Student@123"),)
        )
        # Student in Hostel Block C
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (2, 'Bob Student', 'O200002', 'o200002@rguktong.ac.in', '9876543211', 'Hostel Block C', '305', ?)
            """,
            (generate_password_hash("Student@123"),)
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

    def setUp(self):
        with self.client.session_transaction() as sess:
            sess.clear()

    # =========================================================================
    # SCENARIO 1: Individual complaint creation remains independent
    # =========================================================================
    def test_scenario_1_individual_complaint_independent(self):
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["student_name"] = "Alice Student"
            sess["id_no"] = "O200001"
            sess["hostel"] = "Hostel Block A"

        response = self.client.post(
            "/add_complaint",
            data={
                "category": "Carpentry",
                "priority": "Low",
                "title": "Broken study chair leg in Room 201",
                "description": "One of the wooden chair legs is broken and wobbles when seated."
            },
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

        conn = get_db_connection()
        complaint = conn.execute(
            "SELECT * FROM complaints WHERE title = ?",
            ("Broken study chair leg in Room 201",)
        ).fetchone()
        conn.close()

        self.assertIsNotNone(complaint)
        self.assertIsNone(complaint["common_issue_id"], "Individual complaint must not link to any common issue")
        self.assertEqual(complaint["status"], "Pending")
        self.assertEqual(complaint["category"], "Carpentry")

    # =========================================================================
    # SCENARIO 2: 10 students reporting same water issue in Hostel Block A
    # =========================================================================
    def test_scenario_2_ten_students_grouping(self):
        conn = get_db_connection()
        # Create the master common issue for Hostel Block A
        issue_id = create_common_issue(
            title="Water Supply Failure in Hostel Block A",
            category="Plumbing",
            hostel="Hostel Block A",
            location_details="Hostel Block A All Washrooms",
            description="Main overhead tank valve failed. No running water across Hostel Block A.",
            priority="High",
            assigned_to="Campus Plumbing Supervisor",
            admin_remarks="Plumbing contractor called for pump replacement",
            created_by="Admin",
            conn=conn
        )
        self.assertIsNotNone(issue_id)

        # Seed 10 distinct students in Hostel Block A
        for i in range(10, 20):
            conn.execute(
                """
                INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
                VALUES (?, ?, ?, ?, '9876543200', 'Hostel Block A', ?, ?)
                """,
                (
                    i,
                    f"Student {i}",
                    f"O2000{i}",
                    f"o2000{i}@rguktong.ac.in",
                    f"A-{i}",
                    generate_password_hash("Student@123")
                )
            )
        conn.commit()
        conn.close()

        # Submit complaints from all 10 students
        complaint_ids = []
        for i in range(10, 20):
            with self.client.session_transaction() as sess:
                sess["student_id"] = i
                sess["student_name"] = f"Student {i}"
                sess["id_no"] = f"O2000{i}"
                sess["hostel"] = "Hostel Block A"

            resp = self.client.post(
                "/add_complaint",
                data={
                    "category": "Plumbing",
                    "priority": "High",
                    "title": "Water supply stopped in Hostel Block A washrooms",
                    "description": "There is completely no water supply running in the washrooms of Hostel Block A."
                },
                follow_redirects=True
            )
            self.assertEqual(resp.status_code, 200)

        # Verify all 10 are automatically linked to issue_id
        conn = get_db_connection()
        linked = conn.execute(
            "SELECT id, common_issue_id, status FROM complaints WHERE common_issue_id = ?",
            (issue_id,)
        ).fetchall()
        stats = get_common_issue_with_stats(issue_id, conn)
        conn.close()

        self.assertEqual(len(linked), 10, "All 10 student complaints must be linked to the common issue")
        self.assertEqual(stats["affected_count"], 10)
        self.issue_id = issue_id

    # =========================================================================
    # SCENARIOS 3 & 4: 1,000 mock students updated ONCE by admin in single query
    # =========================================================================
    def test_scenario_3_and_4_one_thousand_students_single_action_update(self):
        conn = get_db_connection()
        issue = conn.execute(
            "SELECT id FROM common_issues WHERE hostel = 'Hostel Block A' AND category = 'Plumbing' LIMIT 1"
        ).fetchone()
        issue_id = issue["id"]

        # Insert 1,000 mock complaints directly linked to this common issue
        mock_complaints = []
        for i in range(100, 1100):
            mock_complaints.append((
                1,  # student_id
                "Plumbing",
                f"No water in washroom tap #{i}",
                "Water supply outage affecting Hostel Block A",
                "High",
                "Pending",
                issue_id
            ))

        conn.executemany(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status, common_issue_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            mock_complaints
        )
        conn.commit()

        # Count total linked complaints before update
        count_before = conn.execute(
            "SELECT COUNT(*) as cnt FROM complaints WHERE common_issue_id = ?",
            (issue_id,)
        ).fetchone()["cnt"]
        self.assertGreaterEqual(count_before, 1000)

        # Time the single admin update operation
        start_time = time.time()
        affected = update_common_issue_once(
            common_issue_id=issue_id,
            status="Resolved",
            remarks="Main pump replaced and water supply restored to full capacity.",
            assigned_to="Senior Campus Engineer",
            updated_by="Chief Administrator",
            conn=conn
        )
        duration = time.time() - start_time

        # Verify performance: single query execution must be sub-second
        self.assertLess(duration, 2.0, f"Single-action update took {duration:.4f}s; must be < 2.0s")
        self.assertEqual(affected, count_before, "All linked complaints must be updated in single statement")

        # Verify all linked complaints have status='Resolved' and updated remarks
        unresolved_count = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM complaints
            WHERE common_issue_id = ? AND (status != 'Resolved' OR remarks NOT LIKE '%pump replaced%')
            """,
            (issue_id,)
        ).fetchone()["cnt"]
        self.assertEqual(unresolved_count, 0, "Zero complaints should remain unresolved")

        # Verify master issue status and audit history
        master = conn.execute("SELECT status, admin_remarks FROM common_issues WHERE id = ?", (issue_id,)).fetchone()
        self.assertEqual(master["status"], "Resolved")
        self.assertIn("pump replaced", master["admin_remarks"])

        history = conn.execute("SELECT * FROM common_issue_history WHERE common_issue_id = ?", (issue_id,)).fetchall()
        self.assertGreaterEqual(len(history), 1)

        # Verify common notification was created
        notifs = conn.execute("SELECT * FROM common_issue_notifications WHERE common_issue_id = ?", (issue_id,)).fetchall()
        self.assertGreaterEqual(len(notifs), 1)

        conn.close()

    # =========================================================================
    # SCENARIO 5: Admin common remarks visible to all affected students
    # =========================================================================
    def test_scenario_5_student_views_admin_remarks(self):
        conn = get_db_connection()
        issue = conn.execute(
            "SELECT id FROM common_issues WHERE hostel = 'Hostel Block A' AND category = 'Plumbing' LIMIT 1"
        ).fetchone()
        issue_id = issue["id"]
        sample_complaint = conn.execute(
            "SELECT id, student_id FROM complaints WHERE common_issue_id = ? LIMIT 1",
            (issue_id,)
        ).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess["student_id"] = sample_complaint["student_id"]
            sess["student_name"] = "Alice Student"
            sess["id_no"] = "O200001"
            sess["hostel"] = "Hostel Block A"

        resp = self.client.get(f"/complaint/{sample_complaint['id']}")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Verify master banner and admin remarks are present in student view
        self.assertIn("Common Issue", html)
        self.assertIn("Resolved", html)
        self.assertIn("Main pump replaced and water supply restored to full capacity.", html)

    # =========================================================================
    # SCENARIO 6: New student filing after common issue exists is auto-linked
    # =========================================================================
    def test_scenario_6_new_student_auto_linked(self):
        conn = get_db_connection()
        # Create an ongoing common issue in Hostel Block B
        issue_id = create_common_issue(
            title="Internet Connectivity Outage in Hostel Block B",
            category="Internet / Wi-Fi",
            hostel="Hostel Block B",
            location_details="Hostel Block B All Floors",
            description="Main network switch failed. No Wi-Fi access across Hostel Block B.",
            priority="High",
            assigned_to="Network Engineer",
            admin_remarks="Technician dispatched to replace hardware.",
            created_by="Admin",
            conn=conn
        )
        conn.execute("UPDATE common_issues SET status = 'In Progress' WHERE id = ?", (issue_id,))

        # Seed student 1001 in Hostel Block B
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (1001, 'Late Comer', 'O200999', 'o200999@rguktong.ac.in', '9876543299', 'Hostel Block B', 'B-404', ?)
            """,
            (generate_password_hash("Student@123"),)
        )
        conn.commit()
        conn.close()

        with self.client.session_transaction() as sess:
            sess["student_id"] = 1001
            sess["student_name"] = "Late Comer"
            sess["id_no"] = "O200999"
            sess["hostel"] = "Hostel Block B"

        resp = self.client.post(
            "/add_complaint",
            data={
                "category": "Internet / Wi-Fi",
                "priority": "High",
                "title": "Internet connectivity outage in Hostel Block B",
                "description": "No Wi-Fi access in rooms across Hostel Block B."
            },
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)

        conn = get_db_connection()
        new_complaint = conn.execute(
            "SELECT * FROM complaints WHERE student_id = 1001 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()

        self.assertIsNotNone(new_complaint)
        self.assertEqual(new_complaint["common_issue_id"], issue_id, "New complaint must be automatically linked")
        self.assertEqual(new_complaint["status"], "In Progress", "Inherits master issue ongoing status")

    # =========================================================================
    # SCENARIO 7: Location safety test: Hostel Block A vs Hostel Block C
    # =========================================================================
    def test_scenario_7_location_safety_different_hostels_never_merge(self):
        # Student in Hostel Block C submits same text description
        with self.client.session_transaction() as sess:
            sess["student_id"] = 2
            sess["student_name"] = "Bob Student"
            sess["id_no"] = "O200002"
            sess["hostel"] = "Hostel Block C"

        resp = self.client.post(
            "/add_complaint",
            data={
                "category": "Plumbing",
                "priority": "High",
                "title": "Water supply stopped in washrooms",
                "description": "No water running in washroom taps."
            },
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)

        conn = get_db_connection()
        block_c_complaint = conn.execute(
            "SELECT * FROM complaints WHERE student_id = 2 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        block_a_issue = conn.execute(
            "SELECT id FROM common_issues WHERE hostel = 'Hostel Block A' AND category = 'Plumbing' LIMIT 1"
        ).fetchone()
        conn.close()

        self.assertIsNotNone(block_c_complaint)
        # Verify Block C complaint did NOT merge into Block A issue
        self.assertNotEqual(
            block_c_complaint["common_issue_id"],
            block_a_issue["id"],
            "Location Safety Violation: Complaint from Hostel Block C merged into Hostel Block A issue!"
        )

    # =========================================================================
    # SCENARIO 8: Student privacy verification: Zero personal peer data in payload
    # =========================================================================
    def test_scenario_8_student_privacy_no_peer_info(self):
        conn = get_db_connection()
        issue = conn.execute(
            "SELECT id FROM common_issues WHERE hostel = 'Hostel Block A' AND category = 'Plumbing' LIMIT 1"
        ).fetchone()
        complaint = conn.execute(
            "SELECT id FROM complaints WHERE common_issue_id = ? AND student_id = 1 LIMIT 1",
            (issue["id"],)
        ).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["student_name"] = "Alice Student"
            sess["id_no"] = "O200001"
            sess["hostel"] = "Hostel Block A"

        resp = self.client.get(f"/complaint/{complaint['id']}")
        html = resp.data.decode("utf-8")

        # Peer students inserted in Scenario 2 had names "Student 10", "Student 11", ID "O200010", etc.
        for peer_id in range(10, 20):
            self.assertNotIn(f"Student {peer_id}", html, f"Privacy violation: peer student name found in HTML")
            self.assertNotIn(f"O2000{peer_id}", html, f"Privacy violation: peer student ID found in HTML")
            self.assertNotIn(f"o2000{peer_id}@rguktong.ac.in", html, f"Privacy violation: peer email found in HTML")

    # =========================================================================
    # SCENARIO 9: Existing functionality regression test
    # =========================================================================
    def test_scenario_9_existing_functionality_regression(self):
        # 1. Admin login
        resp = self.client.post(
            "/admin_login",
            data={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD},
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)

        # 2. Admin dashboard access
        resp = self.client.get("/admin_dashboard")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Admin Dashboard", resp.data.decode("utf-8"))

        # 3. Common issues list view
        resp = self.client.get("/admin/common_issues")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Master Common Issues", resp.data.decode("utf-8"))

        # 4. Manage complaints view
        resp = self.client.get("/manage_complaints")
        self.assertEqual(resp.status_code, 200)

        # 5. Admin single complaint update
        conn = get_db_connection()
        c = conn.execute("SELECT id FROM complaints WHERE common_issue_id IS NULL LIMIT 1").fetchone()
        conn.close()
        if c:
            resp = self.client.post(
                f"/update_status/{c['id']}",
                data={"status": "In Progress", "remarks": "Assigned carpenter", "assigned_to": "Mr. Rao"},
                follow_redirects=True
            )
            self.assertEqual(resp.status_code, 200)

        # 6. Student dashboard & notifications
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["student_name"] = "Alice Student"
            sess["id_no"] = "O200001"
            sess["hostel"] = "Hostel Block A"

        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/notifications")
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/activity")
        self.assertEqual(resp.status_code, 200)

        # 7. 404 Handler
        resp = self.client.get("/non_existent_url_12345")
        self.assertEqual(resp.status_code, 404)

if __name__ == "__main__":
    unittest.main()
