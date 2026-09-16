import os
import sys
import unittest
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

venv_site = os.path.join(BASE_DIR, ".venv", "lib", "python3.13", "site-packages")
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.append(venv_site)

import config

TEST_DB_PATH = os.path.join(BASE_DIR, "test_notifications.db")
config.DATABASE_URL = ""
config.DATABASE = TEST_DB_PATH
config.SECRET_KEY = "test-notifications-secret-123"

os.environ["TESTING"] = "1"
from app import create_app
from database.db import get_db_connection
from database.queries import init_database
from services.notification_service import (
    get_student_notifications,
    archive_single_notification,
    unarchive_single_notification,
    archive_all_read_notifications,
    auto_archive_notifications,
)
from services.common_issue_service import (
    create_common_issue,
    associate_complaint_to_common_issue,
)


class TestArchivedNotifications(unittest.TestCase):
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

        # Seed two students for isolation testing
        conn = get_db_connection()
        pw_hash = generate_password_hash("Pass1234!")
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (1, 'Student One', 'O220001', 'o220001@rguktong.ac.in', '9876543210', 'BH-1', '101', ?)
            """,
            (pw_hash,)
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (2, 'Student Two', 'O220002', 'o220002@rguktong.ac.in', '9876543211', 'BH-1', '102', ?)
            """,
            (pw_hash,)
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
        conn = get_db_connection()
        conn.execute("DELETE FROM notifications")
        conn.execute("DELETE FROM notification_reads")
        conn.execute("DELETE FROM common_issue_notifications")
        conn.execute("DELETE FROM complaints")
        conn.execute("DELETE FROM common_issues")
        conn.commit()
        conn.close()
        self._login_student_1()

    def _login_student_1(self):
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["id_no"] = "O220001"
            sess["student_name"] = "Student One"

    def _login_student_2(self):
        with self.client.session_transaction() as sess:
            sess["student_id"] = 2
            sess["id_no"] = "O220002"
            sess["student_name"] = "Student Two"

    def test_01_notifications_active_view_renders_200(self):
        """Test 1: /notifications (default view) returns HTTP 200 with notification center markup."""
        res = self.client.get("/notifications")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Notification Center", html)
        self.assertIn("Active Inbox", html)

    def test_02_notifications_archived_view_renders_200(self):
        """Test 2: /notifications?view=archived returns HTTP 200 and never 500."""
        res = self.client.get("/notifications?view=archived")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Notification Center", html)
        self.assertIn("Notification History", html)

    def test_03_empty_archived_notifications(self):
        """Test 3: Empty archived notifications view renders friendly empty-state markup."""
        res = self.client.get("/notifications?view=archived")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("No Archived Notifications", html)
        self.assertIn("Your notification history is empty", html)

    def test_04_archived_notifications_with_records(self):
        """Test 4: Creating and archiving a single individual notification displays it in archived view."""
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO notifications (student_id, message, is_read, is_archived, archived_at, created_at)
            VALUES (1, 'Your water purifier complaint has been resolved.', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        conn.commit()
        conn.close()

        res = self.client.get("/notifications?view=archived")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Your water purifier complaint has been resolved.", html)
        self.assertIn("Restore to Inbox", html)
        self.assertIn("Archived", html)

    def test_05_multiple_archived_notifications_ordering(self):
        """Test 5: Multiple archived notifications are correctly ordered by archived_at / created_at DESC."""
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO notifications (student_id, message, is_read, is_archived, archived_at, created_at)
            VALUES (1, 'Earlier archived notification #1', 1, 1, '2026-01-01 10:00:00', '2026-01-01 09:00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO notifications (student_id, message, is_read, is_archived, archived_at, created_at)
            VALUES (1, 'Later archived notification #2', 1, 1, '2026-01-02 10:00:00', '2026-01-02 09:00:00')
            """
        )
        conn.commit()
        conn.close()

        data = get_student_notifications(student_id=1, view="archived")
        self.assertGreaterEqual(len(data["items"]), 2)
        # Verify ordering: later notification should appear before earlier
        messages = [item["message"] for item in data["items"]]
        idx2 = messages.index("Later archived notification #2")
        idx1 = messages.index("Earlier archived notification #1")
        self.assertLess(idx2, idx1, "Later archived notification must appear before earlier archived notification")

    def test_06_common_issue_notifications_archived(self):
        """Test 6: Common Issue notifications can be marked as read and archived."""
        conn = get_db_connection()
        ci_id = create_common_issue(
            title="BH-1 1st Floor Wi-Fi Downtime",
            category="Internet / Wi-Fi",
            hostel="BH-1",
            location_details="1st Floor Corridor",
            description="Router fiber disconnected",
            priority="High",
            conn=conn
        )
        # Create complaint for student 1 linked to common issue
        cur = conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status, common_issue_id)
            VALUES (1, 'Internet / Wi-Fi', 'Wi-Fi not working', 'No signal', 'High', 'In Progress', ?)
            """,
            (ci_id,)
        )
        # Create common issue notification
        cur_cin = conn.execute(
            """
            INSERT INTO common_issue_notifications (common_issue_id, message, created_at)
            VALUES (?, 'Update on BH-1 1st Floor Wi-Fi: Technician dispatched.', CURRENT_TIMESTAMP)
            """,
            (ci_id,)
        )
        cin_id = cur_cin.lastrowid
        conn.commit()
        conn.close()

        # Archive this common issue notification for student 1
        success = archive_single_notification(student_id=1, notif_id=cin_id, notif_type="common")
        self.assertTrue(success)

        # Check archived view
        data = get_student_notifications(student_id=1, view="archived")
        found = any(item["id"] == cin_id and item["notif_type"] == "common" for item in data["items"])
        self.assertTrue(found, "Archived common issue notification must appear in archived list")

        # Unarchive and check active view
        unarchive_single_notification(student_id=1, notif_id=cin_id, notif_type="common")
        data_active = get_student_notifications(student_id=1, view="active")
        found_active = any(item["id"] == cin_id and item["notif_type"] == "common" for item in data_active["items"])
        self.assertTrue(found_active, "Restored common issue notification must appear in active list")

    def test_07_duplicate_notification_prevention(self):
        """Test 7: A student with multiple complaints under the same common issue receives only 1 notification."""
        conn = get_db_connection()
        ci_id = create_common_issue(
            title="Water Pipeline Repair BH-1",
            category="Plumbing",
            hostel="BH-1",
            location_details="Main Line",
            description="Pipeline maintenance",
            priority="Medium",
            conn=conn
        )
        # Two complaints by Student 1 under the same Common Issue
        conn.execute(
            "INSERT INTO complaints (student_id, category, title, description, priority, status, common_issue_id) VALUES (1, 'Plumbing', 'Tap A', 'Leaking', 'Medium', 'Pending', ?)",
            (ci_id,)
        )
        conn.execute(
            "INSERT INTO complaints (student_id, category, title, description, priority, status, common_issue_id) VALUES (1, 'Plumbing', 'Tap B', 'Low pressure', 'Medium', 'Pending', ?)",
            (ci_id,)
        )
        cur_cin = conn.execute(
            "INSERT INTO common_issue_notifications (common_issue_id, message, created_at) VALUES (?, 'Pipeline work in progress.', CURRENT_TIMESTAMP)",
            (ci_id,)
        )
        cin_id = cur_cin.lastrowid
        # Mark as archived for student 1
        conn.execute(
            "INSERT INTO notification_reads (common_issue_notification_id, student_id, is_archived, archived_at) VALUES (?, 1, 1, CURRENT_TIMESTAMP)",
            (cin_id,)
        )
        conn.commit()
        conn.close()

        data = get_student_notifications(student_id=1, view="archived")
        matching = [item for item in data["items"] if item["id"] == cin_id and item["notif_type"] == "common"]
        self.assertEqual(len(matching), 1, "Expected exactly 1 deduplicated common issue notification")

    def test_08_pagination_in_archived_view(self):
        """Test 8: Pagination parameters (page, per_page, total_pages) function accurately."""
        conn = get_db_connection()
        for i in range(25):
            conn.execute(
                """
                INSERT INTO notifications (student_id, message, is_read, is_archived, archived_at, created_at)
                VALUES (1, ?, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (f"Paginated archived notice #{i+1}",)
            )
        conn.commit()
        conn.close()

        page1 = get_student_notifications(student_id=1, view="archived", page=1, per_page=10)
        self.assertEqual(page1["page"], 1)
        self.assertEqual(page1["per_page"], 10)
        self.assertEqual(len(page1["items"]), 10)
        self.assertGreaterEqual(page1["total_pages"], 3)

        page2 = get_student_notifications(student_id=1, view="archived", page=2, per_page=10)
        self.assertEqual(page2["page"], 2)
        self.assertEqual(len(page2["items"]), 10)
        # Ensure page 1 and page 2 items are distinct
        p1_msgs = {it["message"] for it in page1["items"]}
        p2_msgs = {it["message"] for it in page2["items"]}
        self.assertTrue(p1_msgs.isdisjoint(p2_msgs))

    def test_09_student_isolation(self):
        """Test 9: Student A's archived notifications are strictly isolated from Student B."""
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO notifications (student_id, message, is_read, is_archived, archived_at, created_at)
            VALUES (1, 'Confidential notice for Student 1 only', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        conn.execute(
            """
            INSERT INTO notifications (student_id, message, is_read, is_archived, archived_at, created_at)
            VALUES (2, 'Confidential notice for Student 2 only', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        conn.commit()
        conn.close()

        # Check Student 1 view
        s1_data = get_student_notifications(student_id=1, view="archived")
        s1_msgs = [it["message"] for it in s1_data["items"]]
        self.assertIn("Confidential notice for Student 1 only", s1_msgs)
        self.assertNotIn("Confidential notice for Student 2 only", s1_msgs)

        # Check Student 2 view
        s2_data = get_student_notifications(student_id=2, view="archived")
        s2_msgs = [it["message"] for it in s2_data["items"]]
        self.assertIn("Confidential notice for Student 2 only", s2_msgs)
        self.assertNotIn("Confidential notice for Student 1 only", s2_msgs)

    def test_10_postgresql_compatible_sql_syntax(self):
        """Test 10: Verify both archived and active SQL queries execute with valid SQL syntax without DISTINCT ORDER BY issues."""
        conn = get_db_connection()
        # Test the archived common issues subquery directly
        cur_archived = conn.execute(
            """
            SELECT * FROM (
                SELECT DISTINCT cin.id, ? AS student_id, cin.message,
                       1 AS is_read,
                       1 AS is_archived,
                       nr.archived_at,
                       cin.created_at, 'common' AS notif_type
                FROM common_issue_notifications cin
                JOIN complaints c ON c.common_issue_id = cin.common_issue_id
                JOIN notification_reads nr ON nr.common_issue_notification_id = cin.id AND nr.student_id = ?
                WHERE c.student_id = ? AND nr.is_archived = 1
            ) sub
            ORDER BY COALESCE(archived_at, created_at) DESC
            """,
            (1, 1, 1)
        )
        rows_archived = cur_archived.fetchall()
        self.assertIsInstance(rows_archived, list)

        # Test the active common issues subquery directly
        cur_active = conn.execute(
            """
            SELECT * FROM (
                SELECT DISTINCT cin.id, ? AS student_id, cin.message,
                       CASE WHEN nr.id IS NOT NULL THEN 1 ELSE 0 END AS is_read,
                       COALESCE(nr.is_archived, 0) AS is_archived,
                       nr.archived_at,
                       cin.created_at, 'common' AS notif_type
                FROM common_issue_notifications cin
                JOIN complaints c ON c.common_issue_id = cin.common_issue_id
                LEFT JOIN notification_reads nr ON nr.common_issue_notification_id = cin.id AND nr.student_id = ?
                WHERE c.student_id = ? AND (nr.is_archived = 0 OR nr.is_archived IS NULL)
            ) sub
            ORDER BY created_at DESC
            """,
            (1, 1, 1)
        )
        rows_active = cur_active.fetchall()
        self.assertIsInstance(rows_active, list)
        conn.close()

    def test_11_mark_all_as_read_button_exists_in_active_view(self):
        """Test 11: GET /notifications visibly includes the 'Mark All as Read' button in the active inbox topbar."""
        res = self.client.get("/notifications")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Mark All as Read", html)
        self.assertIn("btn-mark-all-read", html)
        self.assertTrue("notifications/read_all" in html or "notifications/read-all" in html)
        self.assertIn("fa-check-double", html)

    def test_12_mark_all_as_read_flow_and_student_isolation(self):
        """Test 12: Mark All as Read marks only current student's unread notifications as read, leaving others and archive untouched."""
        conn = get_db_connection()
        # Student 1: 3 unread notifications + 1 archived notification
        for i in range(3):
            conn.execute(
                "INSERT INTO notifications (student_id, message, is_read, is_archived, created_at) VALUES (1, ?, 0, 0, CURRENT_TIMESTAMP)",
                (f"Student 1 unread notice #{i+1}",)
            )
        conn.execute(
            "INSERT INTO notifications (student_id, message, is_read, is_archived, archived_at, created_at) VALUES (1, 'Student 1 pre-archived notice', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        # Student 2: 2 unread notifications
        for i in range(2):
            conn.execute(
                "INSERT INTO notifications (student_id, message, is_read, is_archived, created_at) VALUES (2, ?, 0, 0, CURRENT_TIMESTAMP)",
                (f"Student 2 unread notice #{i+1}",)
            )
        conn.commit()
        conn.close()

        # Check initial unread counts
        s1_data = get_student_notifications(student_id=1, view="active")
        self.assertEqual(s1_data["unread_total"], 3)
        s2_data = get_student_notifications(student_id=2, view="active")
        self.assertEqual(s2_data["unread_total"], 2)

        # Student 1 triggers Mark All as Read
        res = self.client.post("/notifications/read-all", data={"view": "active"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify Student 1: 0 unread, active notifications are read
        s1_after = get_student_notifications(student_id=1, view="active")
        self.assertEqual(s1_after["unread_total"], 0)
        self.assertEqual(s1_after["active_total"], 3)
        for item in s1_after["items"]:
            self.assertEqual(item["is_read"], 1)

        # Verify Student 1's archived notice is still archived
        s1_archived = get_student_notifications(student_id=1, view="archived")
        self.assertEqual(s1_archived["archived_total"], 1)

        # Verify Student 2's unread notifications are STILL unread (isolation)
        s2_after = get_student_notifications(student_id=2, view="active")
        self.assertEqual(s2_after["unread_total"], 2)
        for item in s2_after["items"]:
            self.assertEqual(item["is_read"], 0)

        # Verify Archive All Read operates separately on the now-read notifications
        res_arch = self.client.post("/notifications/archive-all", follow_redirects=True)
        self.assertEqual(res_arch.status_code, 200)
        s1_arch_after = get_student_notifications(student_id=1, view="archived")
        self.assertEqual(s1_arch_after["archived_total"], 4)

    def test_13_mark_all_as_read_when_empty_or_already_read(self):
        """Test 13: Mark All as Read when no unread notifications exist safely returns HTTP 200 without 500 error."""
        res = self.client.post("/notifications/read-all", data={"view": "active"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Notification Center", html)


if __name__ == "__main__":
    unittest.main()
