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

os.environ["TESTING"] = "1"
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

    # =========================================================================
    # SCENARIO 10: Status-Aware Grouping for Recurrent Complaints After Resolution
    # =========================================================================
    def test_scenario_10_resolved_common_issue_not_reopened_creates_new_issue(self):
        """
        Exact user scenario:
        1. Common Issue X exists with Complaint A ('No water', Room 108).
        2. Admin resolves Common Issue X.
        3. A student submits a NEW Complaint B ('no water', Room 108).
        4. The system detects similarity, checks matching issue status (Resolved -> Inactive),
           and creates a NEW Common Issue Y in 'Pending' status.
        5. Complaint B is linked to NEW Common Issue Y (NOT old resolved Common Issue X).
        """
        conn = get_db_connection()
        # Create Common Issue X in Hostel Block A
        issue_x_id = create_common_issue(
            title="Hostel Block A - No water",
            category="Water",
            hostel="Hostel Block A",
            location_details="Room 108 and 1st floor",
            description="No water supply in Room 108 washroom.",
            priority="High",
            created_by="Admin",
            conn=conn
        )
        # Create Complaint A and link to Issue X
        cur = conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status, common_issue_id)
            VALUES (1, 'Water', 'No water', 'Water problem in Room 108.', 'High', 'Pending', ?)
            """,
            (issue_x_id,)
        )
        comp_a_id = cur.lastrowid
        conn.commit()

        # Admin resolves Common Issue X via single-action master update
        affected = update_common_issue_once(
            common_issue_id=issue_x_id,
            status="Resolved",
            remarks="Replaced faulty valve on 1st floor.",
            assigned_to="Plumber Ramesh",
            updated_by="Hostel Administration",
            conn=conn
        )
        self.assertEqual(affected, 1)

        # Verify Issue X and Complaint A are both Resolved
        issue_x = conn.execute("SELECT status FROM common_issues WHERE id = ?", (issue_x_id,)).fetchone()
        comp_a = conn.execute("SELECT status, common_issue_id FROM complaints WHERE id = ?", (comp_a_id,)).fetchone()
        self.assertEqual(issue_x["status"], "Resolved")
        self.assertEqual(comp_a["status"], "Resolved")
        self.assertEqual(comp_a["common_issue_id"], issue_x_id)

        # Seed student 2001 living in Hostel Block A
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (2001, 'Charlie Student', 'O200888', 'o200888@rguktong.ac.in', '9876543288', 'Hostel Block A', 'A-108', ?)
            """,
            (generate_password_hash("Student@123"),)
        )
        conn.commit()
        conn.close()

        # Later, student 2001 submits a new Complaint B: "no water" in Room 108
        with self.client.session_transaction() as sess:
            sess["student_id"] = 2001
            sess["student_name"] = "Charlie Student"
            sess["id_no"] = "O200888"
            sess["hostel"] = "Hostel Block A"

        resp = self.client.post(
            "/add_complaint",
            data={
                "category": "Water",
                "priority": "High",
                "title": "no water",
                "description": "Drinking and tap water issue in Room 108."
            },
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)

        conn = get_db_connection()
        comp_b = conn.execute(
            "SELECT * FROM complaints WHERE student_id = 2001 AND title = 'no water' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(comp_b)

        # Crucial checks:
        # 1. Complaint B must NOT be linked to resolved Common Issue X!
        self.assertNotEqual(comp_b["common_issue_id"], issue_x_id, "Must NOT link new complaint to resolved common issue")
        self.assertIsNotNone(comp_b["common_issue_id"], "Must create a new common issue for the new occurrence")

        # 2. Complaint B must be linked to a brand NEW Common Issue Y
        issue_y_id = comp_b["common_issue_id"]
        issue_y = conn.execute("SELECT * FROM common_issues WHERE id = ?", (issue_y_id,)).fetchone()
        self.assertIsNotNone(issue_y)
        self.assertEqual(issue_y["status"], "Pending", "New common issue must start in Pending status")
        self.assertEqual(comp_b["status"], "Pending", "New complaint must have status Pending, NOT Resolved")

        # 3. Old Common Issue X must still be intact and resolved
        issue_x_after = conn.execute("SELECT * FROM common_issues WHERE id = ?", (issue_x_id,)).fetchone()
        self.assertEqual(issue_x_after["status"], "Resolved")
        comp_a_after = conn.execute("SELECT * FROM complaints WHERE id = ?", (comp_a_id,)).fetchone()
        self.assertEqual(comp_a_after["common_issue_id"], issue_x_id)

        # 4. If a 3rd complaint arrives now for the same issue, it MUST link to active Issue Y!
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["student_name"] = "Alice Student"
            sess["id_no"] = "O200001"
            sess["hostel"] = "Hostel Block A"

        resp3 = self.client.post(
            "/add_complaint",
            data={
                "category": "Water",
                "priority": "High",
                "title": "water problem again",
                "description": "No water flow in Room 108."
            },
            follow_redirects=True
        )
        self.assertEqual(resp3.status_code, 200)

        comp_c = conn.execute(
            "SELECT * FROM complaints WHERE student_id = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(comp_c["common_issue_id"], issue_y_id, "Subsequent complaint must link to the currently active Issue Y")
        conn.close()

    # =========================================================================
    # SCENARIO 11: Explicit Verification of Points A, B, C, D, E & Dashboard Counts
    # =========================================================================
    def test_scenario_11_verification_points_a_through_e_and_dashboard_counts(self):
        """
        Validates the 5 explicit verification points and dashboard metrics:
        A. Active Common Issue + similar new complaint -> joins existing active issue.
        B. Resolved Common Issue + similar new complaint -> creates NEW issue in Pending status.
        C. New complaint after recurrence -> joins the new active Common Issue.
        D. Different location/problem -> does not incorrectly group.
        E. Historical resolved Common Issue -> remains completely unchanged.
        Counts: Verifies Common Issues list and Admin Dashboard active counts.
        """
        conn = get_db_connection()

        # Clean slate for this scenario in isolated test database
        conn.execute("DELETE FROM common_issue_notifications")
        conn.execute("DELETE FROM notification_reads")
        conn.execute("DELETE FROM common_issue_history")
        conn.execute("DELETE FROM complaint_history")
        conn.execute("DELETE FROM complaints")
        conn.execute("DELETE FROM common_issues")

        # Seed students in Hostel Block A and Hostel Block B
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (3001, 'Student A1', 'O300001', 'o300001@rguktong.ac.in', '9876543001', 'Hostel Block A', 'A-101', ?)
            """,
            (generate_password_hash("Student@123"),)
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (3002, 'Student A2', 'O300002', 'o300002@rguktong.ac.in', '9876543002', 'Hostel Block A', 'A-102', ?)
            """,
            (generate_password_hash("Student@123"),)
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (3003, 'Student A3', 'O300003', 'o300003@rguktong.ac.in', '9876543003', 'Hostel Block A', 'A-103', ?)
            """,
            (generate_password_hash("Student@123"),)
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (3004, 'Student B1', 'O300004', 'o300004@rguktong.ac.in', '9876543004', 'Hostel Block B', 'B-101', ?)
            """,
            (generate_password_hash("Student@123"),)
        )
        conn.commit()

        # Create Active Common Issue 1 in Hostel Block A
        issue_1_id = create_common_issue(
            title="Hostel Block A - Ceiling Fan Vibration",
            category="Electrical",
            hostel="Hostel Block A",
            location_details="Hostel Block A Wing 1",
            description="Severe ceiling fan vibration and noise.",
            priority="Medium",
            created_by="Admin",
            conn=conn
        )
        # Associate complaint 1 to Issue 1
        cur1 = conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status, common_issue_id)
            VALUES (3001, 'Electrical', 'Ceiling fan vibrating', 'Fan in room A-101 shakes heavily.', 'Medium', 'Pending', ?)
            """,
            (issue_1_id,)
        )
        comp_1_id = cur1.lastrowid
        conn.commit()
        conn.close()

        # ---------------------------------------------------------------------
        # Point A: Active Common Issue + similar new complaint -> joins active issue
        # ---------------------------------------------------------------------
        with self.client.session_transaction() as sess:
            sess["student_id"] = 3002
            sess["student_name"] = "Student A2"
            sess["id_no"] = "O300002"
            sess["hostel"] = "Hostel Block A"

        resp_a = self.client.post(
            "/add_complaint",
            data={
                "category": "Electrical",
                "priority": "Medium",
                "title": "Ceiling fan vibrating violently",
                "description": "Ceiling fan in room A-102 shaking and making noise."
            },
            follow_redirects=True
        )
        self.assertEqual(resp_a.status_code, 200)

        conn = get_db_connection()
        comp_2 = conn.execute(
            "SELECT * FROM complaints WHERE student_id = 3002 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(comp_2["common_issue_id"], issue_1_id, "Point A: Must join existing active issue")

        # ---------------------------------------------------------------------
        # Resolve Common Issue 1
        # ---------------------------------------------------------------------
        affected = update_common_issue_once(
            common_issue_id=issue_1_id,
            status="Resolved",
            remarks="All fan anchor bolts tightened.",
            assigned_to="Electrician Team",
            updated_by="Admin",
            conn=conn
        )
        self.assertEqual(affected, 2)
        conn.close()

        # ---------------------------------------------------------------------
        # Point B: Resolved Common Issue + similar new complaint -> creates NEW Common Issue in Pending
        # ---------------------------------------------------------------------
        with self.client.session_transaction() as sess:
            sess["student_id"] = 3003
            sess["student_name"] = "Student A3"
            sess["id_no"] = "O300003"
            sess["hostel"] = "Hostel Block A"

        resp_b = self.client.post(
            "/add_complaint",
            data={
                "category": "Electrical",
                "priority": "Medium",
                "title": "Ceiling fan vibrating again",
                "description": "Ceiling fan vibration in room A-103 shaking regulator."
            },
            follow_redirects=True
        )
        self.assertEqual(resp_b.status_code, 200)

        conn = get_db_connection()
        comp_3 = conn.execute(
            "SELECT * FROM complaints WHERE student_id = 3003 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(comp_3)
        issue_2_id = comp_3["common_issue_id"]

        self.assertNotEqual(issue_2_id, issue_1_id, "Point B: Must NOT join resolved Common Issue 1")
        self.assertIsNotNone(issue_2_id, "Point B: Must create a NEW Common Issue")

        issue_2 = conn.execute("SELECT * FROM common_issues WHERE id = ?", (issue_2_id,)).fetchone()
        self.assertEqual(issue_2["status"], "Pending", "Point B: New Common Issue must be in Pending status")
        self.assertEqual(comp_3["status"], "Pending", "Point B: New complaint must be in Pending status")

        # ---------------------------------------------------------------------
        # Point C: New complaint after recurrence -> joins the new active Common Issue
        # ---------------------------------------------------------------------
        with self.client.session_transaction() as sess:
            sess["student_id"] = 3001
            sess["student_name"] = "Student A1"
            sess["id_no"] = "O300001"
            sess["hostel"] = "Hostel Block A"

        resp_c = self.client.post(
            "/add_complaint",
            data={
                "category": "Electrical",
                "priority": "Medium",
                "title": "Fan vibration still present",
                "description": "Room A-101 ceiling fan still shaking."
            },
            follow_redirects=True
        )
        self.assertEqual(resp_c.status_code, 200)

        comp_4 = conn.execute(
            "SELECT * FROM complaints WHERE student_id = 3001 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(comp_4["common_issue_id"], issue_2_id, "Point C: Must join the new active Common Issue 2")

        # ---------------------------------------------------------------------
        # Point D: Different location / problem -> does not incorrectly group
        # ---------------------------------------------------------------------
        # D1: Same problem text, but DIFFERENT hostel (Hostel Block B)
        with self.client.session_transaction() as sess:
            sess["student_id"] = 3004
            sess["student_name"] = "Student B1"
            sess["id_no"] = "O300004"
            sess["hostel"] = "Hostel Block B"

        resp_d1 = self.client.post(
            "/add_complaint",
            data={
                "category": "Electrical",
                "priority": "Medium",
                "title": "Ceiling fan vibrating",
                "description": "Ceiling fan shaking in Hostel Block B."
            },
            follow_redirects=True
        )
        self.assertEqual(resp_d1.status_code, 200)

        conn = get_db_connection()
        comp_5 = conn.execute(
            "SELECT * FROM complaints WHERE student_id = 3004 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertNotEqual(comp_5["common_issue_id"], issue_1_id, "Point D: Never merge across different hostels")
        self.assertNotEqual(comp_5["common_issue_id"], issue_2_id, "Point D: Never merge across different hostels")

        # D2: Same hostel (Hostel Block A), but DIFFERENT category / problem (Plumbing leak)
        with self.client.session_transaction() as sess:
            sess["student_id"] = 3002
            sess["student_name"] = "Student A2"
            sess["id_no"] = "O300002"
            sess["hostel"] = "Hostel Block A"

        resp_d2 = self.client.post(
            "/add_complaint",
            data={
                "category": "Plumbing",
                "priority": "High",
                "title": "Washroom flush tank overflowing",
                "description": "Continuous water overflow from flush valve in 1st floor bathroom."
            },
            follow_redirects=True
        )
        self.assertEqual(resp_d2.status_code, 200)

        comp_6 = conn.execute(
            "SELECT * FROM complaints WHERE student_id = 3002 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertNotEqual(comp_6["common_issue_id"], issue_1_id, "Point D: Different problem must not merge into fan issue")
        self.assertNotEqual(comp_6["common_issue_id"], issue_2_id, "Point D: Different problem must not merge into fan issue")

        # ---------------------------------------------------------------------
        # Point E: Historical resolved Common Issue remains completely unchanged
        # ---------------------------------------------------------------------
        issue_1_final = conn.execute("SELECT * FROM common_issues WHERE id = ?", (issue_1_id,)).fetchone()
        self.assertEqual(issue_1_final["status"], "Resolved", "Point E: Historical issue status remains Resolved")
        self.assertEqual(issue_1_final["admin_remarks"], "All fan anchor bolts tightened.")
        self.assertEqual(issue_1_final["assigned_to"], "Electrician Team")

        issue_1_complaints = conn.execute(
            "SELECT id FROM complaints WHERE common_issue_id = ? ORDER BY id ASC", (issue_1_id,)
        ).fetchall()
        issue_1_comp_ids = [r["id"] for r in issue_1_complaints]
        self.assertEqual(issue_1_comp_ids, [comp_1_id, comp_2["id"]], "Point E: Historical issue complaints list unchanged")

        # ---------------------------------------------------------------------
        # Common Issue Counts & Admin Dashboard Verification
        # ---------------------------------------------------------------------
        # Verify Common Issues List route counts
        with self.client.session_transaction() as sess:
            sess["admin"] = config.ADMIN_USERNAME

        res_ci = self.client.get("/admin/common_issues")
        self.assertEqual(res_ci.status_code, 200)
        # Check active and resolved labels in rendered HTML
        self.assertIn(b"Active Issues", res_ci.data)
        self.assertIn(b"Resolved", res_ci.data)

        # Verify Admin Dashboard counts
        res_dash = self.client.get("/admin_dashboard")
        self.assertEqual(res_dash.status_code, 200)

        # Verify exact counts from DB match logic:
        # Total issues: issue_1 (Resolved), issue_2 (Pending) -> 2
        # Active issues: issue_2 (Pending) -> 1
        ci_total = conn.execute("SELECT COUNT(*) FROM common_issues").fetchone()[0]
        ci_active = conn.execute(
            "SELECT COUNT(*) FROM common_issues WHERE LOWER(TRIM(status)) IN ('pending', 'in progress')"
        ).fetchone()[0]
        self.assertEqual(ci_total, 2)
        self.assertEqual(ci_active, 1)

        # ---------------------------------------------------------------------
        # SCENARIO 12: Create Master Issue Modal, DB Creation, and Manual Grouping
        # ---------------------------------------------------------------------
    def test_scenario_12_create_master_issue_modal_and_manual_grouping(self):
        """
        Comprehensive test for:
        1. Create Master Issue modal rendering, scrollability, and form structure.
        2. Admin authorization enforcement.
        3. Form validation (missing required fields).
        4. Successful DB creation and flash message.
        5. Manual linking of unlinked student complaints.
        6. Complaint unlinking and count synchronization.
        """
        # 1. Admin authorization check
        with self.client.session_transaction() as sess:
            sess.clear()

        # Unauthenticated access
        resp_unauth = self.client.post("/admin/common_issue/create", data={"title": "Test"}, follow_redirects=False)
        self.assertEqual(resp_unauth.status_code, 302)
        self.assertIn("/admin_login", resp_unauth.headers.get("Location", ""))

        # Student access (forbidden from admin routes)
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["student_name"] = "Alice Student"
        resp_student = self.client.post("/admin/common_issue/create", data={"title": "Test"}, follow_redirects=False)
        self.assertEqual(resp_student.status_code, 302)
        self.assertIn("/admin_login", resp_student.headers.get("Location", ""))

        # 2. Login as Admin & check Modal rendering on /admin/common_issues
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["admin"] = config.ADMIN_USERNAME

        resp_list = self.client.get("/admin/common_issues")
        self.assertEqual(resp_list.status_code, 200)
        html = resp_list.data.decode("utf-8")

        self.assertIn("createCommonIssueModal", html)
        self.assertIn("modal-dialog-scrollable", html)
        self.assertIn("Create Master Common Issue", html)

        # Verify modal is placed at document root level (outside <main class="page-wrapper">)
        main_end_pos = html.find("</main>")
        modal_pos = html.find('id="createCommonIssueModal"')
        self.assertGreater(modal_pos, main_end_pos, "Modal must be placed outside <main> at root level to prevent backdrop stacking trap")

        # Verify all form controls are present and enabled (NOT disabled or readonly)
        self.assertIn('name="title"', html)
        self.assertIn('name="hostel"', html)
        self.assertIn('name="category"', html)
        self.assertIn('name="priority"', html)
        self.assertIn('name="location_details"', html)
        self.assertIn('name="description"', html)
        self.assertIn('name="assigned_to"', html)
        self.assertIn('name="admin_remarks"', html)
        self.assertIn("Create Master Issue", html)

        # Ensure form inputs are NOT disabled or readonly
        self.assertNotIn('name="title" disabled', html)
        self.assertNotIn('name="hostel" disabled', html)
        self.assertNotIn('name="category" disabled', html)
        self.assertNotIn('name="description" disabled', html)
        self.assertNotIn('name="title" readonly', html)
        self.assertNotIn('name="hostel" readonly', html)

        # 3. Form Validation (Missing required title/hostel/category)
        resp_invalid = self.client.post(
            "/admin/common_issue/create",
            data={
                "title": "",
                "hostel": "Hostel Block A",
                "category": "Plumbing"
            },
            follow_redirects=True
        )
        self.assertEqual(resp_invalid.status_code, 200)
        self.assertIn("Title, category, and hostel location are required", resp_invalid.data.decode("utf-8"))

        # 4. Successful creation of Master Issue
        resp_create = self.client.post(
            "/admin/common_issue/create",
            data={
                "title": "Master Solar Water Heater Failure",
                "hostel": "Hostel Block D",
                "category": "Plumbing",
                "priority": "High",
                "location_details": "Rooftop Solar Array 3",
                "description": "Solar water heater pressure relief valve ruptured.",
                "assigned_to": "Solar Maintenance Contractor",
                "admin_remarks": "Technicians arriving at 10 AM"
            },
            follow_redirects=True
        )
        self.assertEqual(resp_create.status_code, 200)
        self.assertIn("Master issue created successfully.", resp_create.data.decode("utf-8"))

        conn = get_db_connection()
        created_issue = conn.execute(
            "SELECT * FROM common_issues WHERE title = 'Master Solar Water Heater Failure'"
        ).fetchone()
        self.assertIsNotNone(created_issue)
        issue_id = created_issue["id"]
        self.assertEqual(created_issue["hostel"], "Hostel Block D")
        self.assertEqual(created_issue["category"], "Plumbing")
        self.assertEqual(created_issue["priority"], "High")
        self.assertEqual(created_issue["status"], "Pending")
        self.assertEqual(created_issue["assigned_to"], "Solar Maintenance Contractor")

        # 5. Seed unlinked student complaints in Hostel Block D (Plumbing)
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (4001, 'Student D1', 'O400001', 'o400001@rguktong.ac.in', '9876544001', 'Hostel Block D', 'D-101', ?)
            """,
            (generate_password_hash("Student@123"),)
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (4002, 'Student D2', 'O400002', 'o400002@rguktong.ac.in', '9876544002', 'Hostel Block D', 'D-102', ?)
            """,
            (generate_password_hash("Student@123"),)
        )
        cur_c1 = conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status)
            VALUES (4001, 'Plumbing', 'No hot water in D-101', 'Solar hot water is completely cold.', 'High', 'Pending')
            """
        )
        c1_id = cur_c1.lastrowid

        cur_c2 = conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status)
            VALUES (4002, 'Plumbing', 'Cold water in morning D-102', 'Solar line leaking on roof.', 'High', 'Pending')
            """
        )
        c2_id = cur_c2.lastrowid
        conn.commit()
        conn.close()

        # 6. Admin manually links complaint 1 to the master issue
        resp_link1 = self.client.post(
            f"/admin/common_issue/{issue_id}/link",
            data={"complaint_id": str(c1_id)},
            follow_redirects=True
        )
        self.assertEqual(resp_link1.status_code, 200)
        self.assertIn("successfully linked", resp_link1.data.decode("utf-8"))

        # Admin manually links complaint 2 to the master issue
        resp_link2 = self.client.post(
            f"/admin/common_issue/{issue_id}/link",
            data={"complaint_id": str(c2_id)},
            follow_redirects=True
        )
        self.assertEqual(resp_link2.status_code, 200)

        # Verify stats show 2 complaints and 2 affected students
        conn = get_db_connection()
        stats = get_common_issue_with_stats(issue_id, conn)
        self.assertEqual(stats["linked_complaints"], 2)
        self.assertEqual(stats["affected_count"], 2)

        # 7. Admin unlinks complaint 1
        resp_unlink = self.client.post(
            f"/admin/common_issue/{issue_id}/unlink/{c1_id}",
            follow_redirects=True
        )
        self.assertEqual(resp_unlink.status_code, 200)
        self.assertIn(f"Complaint #{c1_id} unlinked", resp_unlink.data.decode("utf-8"))

        # Verify stats updated to 1 complaint and 1 affected student
        stats_after = get_common_issue_with_stats(issue_id, conn)
        self.assertEqual(stats_after["linked_complaints"], 1)
        self.assertEqual(stats_after["affected_count"], 1)

        c1_record = conn.execute("SELECT common_issue_id FROM complaints WHERE id = ?", (c1_id,)).fetchone()
        self.assertIsNone(c1_record["common_issue_id"])
        conn.close()


if __name__ == "__main__":
    unittest.main()
