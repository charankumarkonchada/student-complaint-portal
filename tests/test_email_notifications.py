import os
import sys
import unittest
from unittest.mock import patch, MagicMock

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

venv_site = os.path.join(BASE_DIR, ".venv", "lib", "python3.13", "site-packages")
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.append(venv_site)

import config

TEST_EMAIL_DB = os.path.join(BASE_DIR, "test_email.db")
config.DATABASE_URL = ""
config.DATABASE = TEST_EMAIL_DB
config.SECRET_KEY = "test-email-notifications-secret"

from app import create_app
from database.db import get_db_connection
from database.queries import init_database
from services.email_service import (
    send_email,
    send_complaint_status_email,
    send_common_issue_status_email,
    send_common_issue_broadcast_emails,
    send_complaint_submitted_email
)
from services.common_issue_service import update_common_issue_once


class EmailNotificationTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.DATABASE_URL = ""
        config.DATABASE = TEST_EMAIL_DB
        if os.path.exists(TEST_EMAIL_DB):
            try:
                os.remove(TEST_EMAIL_DB)
            except Exception:
                pass
        init_database()
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_EMAIL_DB):
            try:
                os.remove(TEST_EMAIL_DB)
            except Exception:
                pass

    def setUp(self):
        conn = get_db_connection()
        conn.execute("DELETE FROM notification_reads")
        conn.execute("DELETE FROM common_issue_notifications")
        conn.execute("DELETE FROM notifications")
        conn.execute("DELETE FROM complaint_history")
        conn.execute("DELETE FROM complaints")
        conn.execute("DELETE FROM common_issues")
        conn.execute("DELETE FROM students")

        # Seed test students
        conn.execute(
            """
            INSERT INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (1, 'Charan Student', 'O210001', 'o210001@rguktong.ac.in', '9876543210', 'Hostel Block A', '101', 'pw')
            """
        )
        conn.execute(
            """
            INSERT INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (2, 'Deepthi Student', 'O210002', 'o210002@rguktong.ac.in', '9876543211', 'Hostel Block A', '102', 'pw')
            """
        )
        # Seed complaint 1
        conn.execute(
            """
            INSERT INTO complaints (id, student_id, category, title, description, priority, status)
            VALUES (1, 1, 'Electrical', 'Ceiling fan making noise', 'Noise from fan regulator', 'Medium', 'Pending')
            """
        )
        conn.commit()
        conn.close()

    def test_01_send_email_disabled_via_config(self):
        """Test that send_email returns False and skips SMTP when disabled via config."""
        with patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", False):
            with patch("smtplib.SMTP") as mock_smtp:
                res = send_email("student@example.com", "Test Subject", "Test Body")
                self.assertFalse(res)
                mock_smtp.assert_not_called()

    def test_02_send_email_invalid_or_missing_recipient(self):
        """Test that send_email returns False when recipient is invalid."""
        with patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", True):
            with patch("smtplib.SMTP") as mock_smtp:
                self.assertFalse(send_email("", "Sub", "Body"))
                self.assertFalse(send_email("invalid-email", "Sub", "Body"))
                mock_smtp.assert_not_called()

    def test_03_send_email_missing_credentials(self):
        """Test that send_email returns False when credentials are not configured."""
        with patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", True):
            with patch.object(config, "SMTP_USERNAME", ""):
                with patch("smtplib.SMTP") as mock_smtp:
                    res = send_email("student@example.com", "Sub", "Body")
                    self.assertFalse(res)
                    mock_smtp.assert_not_called()

    def test_04_send_email_smtp_success_tls(self):
        """Test send_email successful flow via smtplib.SMTP with TLS."""
        with patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", True), \
             patch.object(config, "SMTP_USERNAME", "mailer@example.com"), \
             patch.object(config, "SMTP_PASSWORD", "secret123"), \
             patch.object(config, "MAIL_FROM", "mailer@example.com"), \
             patch.object(config, "SMTP_USE_TLS", True):
            with patch("smtplib.SMTP") as mock_smtp_cls:
                mock_instance = MagicMock()
                mock_smtp_cls.return_value.__enter__.return_value = mock_instance

                res = send_email("student@example.com", "Subject", "Plain text", "<p>HTML</p>")
                self.assertTrue(res)
                mock_instance.starttls.assert_called_once()
                mock_instance.login.assert_called_once_with("mailer@example.com", "secret123")
                mock_instance.send_message.assert_called_once()

    def test_05_send_email_resilience_smtp_exception(self):
        """Test that send_email catches exceptions and returns False cleanly."""
        with patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", True), \
             patch.object(config, "SMTP_USERNAME", "mailer@example.com"), \
             patch.object(config, "SMTP_PASSWORD", "secret123"), \
             patch.object(config, "MAIL_FROM", "mailer@example.com"):
            with patch("smtplib.SMTP", side_effect=Exception("SMTP Server Unavailable")):
                res = send_email("student@example.com", "Sub", "Body")
                self.assertFalse(res)

    def test_06_single_complaint_status_update_dispatches_in_app_and_email(self):
        """Test updating individual complaint status triggers in-app notification and email dispatch."""
        with self.client.session_transaction() as sess:
            sess["admin"] = config.ADMIN_USERNAME

        with patch("services.email_service.send_email", return_value=True) as mock_send_email:
            res = self.client.post("/update_status/1", data={
                "status": "Resolved",
                "assigned_to": "Plumber Rajesh",
                "remarks": "Fixed damaged pipe and verified flow."
            }, follow_redirects=True)
            self.assertEqual(res.status_code, 200)

            # In-App Notification check
            conn = get_db_connection()
            notif = conn.execute("SELECT * FROM notifications WHERE student_id = 1 ORDER BY id DESC LIMIT 1").fetchone()
            student = conn.execute("SELECT email FROM students WHERE id = 1").fetchone()
            conn.close()

            self.assertIsNotNone(notif)
            self.assertIn("Resolved", notif["message"])

            # Email dispatch check
            mock_send_email.assert_called_once()
            called_recipient = mock_send_email.call_args.kwargs.get("recipient")
            called_subject = mock_send_email.call_args.kwargs.get("subject")
            self.assertEqual(called_recipient, student["email"])
            self.assertIn("Complaint #1 Status Updated", called_subject)

    def test_07_single_complaint_update_resilient_to_email_failure(self):
        """Test that complaint status update and in-app notification succeed even if email dispatch fails/raises."""
        with self.client.session_transaction() as sess:
            sess["admin"] = config.ADMIN_USERNAME

        with patch("services.email_service.send_complaint_status_email", side_effect=RuntimeError("SMTP crash")):
            res = self.client.post("/update_status/1", data={
                "status": "In Progress",
                "assigned_to": "Technician Anand",
                "remarks": "Work in progress"
            }, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Complaint Updated Successfully", res.data)

            # In-app notification and status MUST still be saved
            conn = get_db_connection()
            complaint = conn.execute("SELECT status FROM complaints WHERE id = 1").fetchone()
            notif = conn.execute("SELECT * FROM notifications WHERE student_id = 1 ORDER BY id DESC LIMIT 1").fetchone()
            conn.close()

            self.assertEqual(complaint["status"], "In Progress")
            self.assertIn("In Progress", notif["message"])

    def test_08_common_issue_broadcast_deduplication(self):
        """
        Test that Common Issue update broadcasts email notifications to distinct students,
        deduplicating when a student has multiple complaints linked to the same common issue.
        """
        conn = get_db_connection()
        # Create a common issue
        cur = conn.execute(
            """
            INSERT INTO common_issues (issue_code, title, category, hostel, status)
            VALUES ('CI-999', 'Water Pressure Failure', 'Water', 'Hostel Block A', 'Pending')
            """
        )
        from database.db import ConnectionAdapter
        ci_id = cur.fetchone()["id"] if isinstance(conn, ConnectionAdapter) else cur.lastrowid

        # Insert 2 complaints for Student 1 and 1 complaint for Student 2
        conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status, common_issue_id)
            VALUES (1, 'Water', 'Low water flow bathroom', 'Detail 1', 'High', 'Pending', ?)
            """,
            (ci_id,)
        )
        conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status, common_issue_id)
            VALUES (1, 'Water', 'No water 2nd floor', 'Detail 2', 'High', 'Pending', ?)
            """,
            (ci_id,)
        )
        conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status, common_issue_id)
            VALUES (2, 'Water', 'Tap dry room 205', 'Detail 3', 'High', 'Pending', ?)
            """,
            (ci_id,)
        )
        conn.commit()

        s1 = conn.execute("SELECT email FROM students WHERE id = 1").fetchone()
        s2 = conn.execute("SELECT email FROM students WHERE id = 2").fetchone()
        conn.close()

        with patch("services.email_service.send_email", return_value=True) as mock_send_email:
            affected = update_common_issue_once(
                common_issue_id=ci_id,
                status="Resolved",
                remarks="Replaced overhead water motor.",
                assigned_to="Hostel Plumbing Team"
            )
            self.assertEqual(affected, 3)

            # Must have sent exactly 2 emails (one for Student 1, one for Student 2), NOT 3!
            self.assertEqual(mock_send_email.call_count, 2)
            recipients = [c.kwargs.get("recipient") for c in mock_send_email.call_args_list]
            self.assertIn(s1["email"], recipients)
            self.assertIn(s2["email"], recipients)
            # Count occurrences of s1["email"]
            self.assertEqual(recipients.count(s1["email"]), 1)
            self.assertEqual(recipients.count(s2["email"]), 1)

    def test_09_complaint_submission_triggers_in_app_and_email(self):
        """Test that submitting a complaint creates an in-app confirmation and sends an email confirmation."""
        # Log in as Student 1
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["role"] = "student"
            sess["name"] = "Charan"
            sess["hostel"] = "Hostel Block A"

        with patch("services.email_service.send_email", return_value=True) as mock_send_email:
            res = self.client.post("/add_complaint", data={
                "category": "Electrical",
                "priority": "High",
                "title": "Study table light socket sparking",
                "description": "Short circuit spark observed when plugging in laptop adapter."
            }, follow_redirects=False)
            self.assertEqual(res.status_code, 302)

            # Verify in-app confirmation notification in DB
            conn = get_db_connection()
            notif = conn.execute(
                "SELECT * FROM notifications WHERE student_id = 1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            student = conn.execute("SELECT email FROM students WHERE id = 1").fetchone()
            conn.close()

            self.assertIsNotNone(notif)
            self.assertIn("submitted successfully", notif["message"])

            # Verify email was dispatched
            mock_send_email.assert_called_once()
            self.assertEqual(mock_send_email.call_args.kwargs.get("recipient"), student["email"])
            self.assertIn("Received", mock_send_email.call_args.kwargs.get("subject"))

    def test_10_reading_notifications_never_sends_email(self):
        """Verify that viewing notifications, marking single read, or mark all as read NEVER triggers an email."""
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["role"] = "student"
            sess["name"] = "Charan"

        with patch("services.email_service.send_email") as mock_send:
            # 1. View notifications page
            res = self.client.get("/notifications")
            self.assertEqual(res.status_code, 200)

            # 2. Mark single notification read
            res = self.client.post("/notification/read/1", data={"notif_type": "individual"})
            self.assertEqual(res.status_code, 302)

            # 3. Mark all as read
            res = self.client.post("/notifications/read-all")
            self.assertEqual(res.status_code, 302)

            res = self.client.post("/notifications/read_all")
            self.assertEqual(res.status_code, 302)

            # Email service must NOT have been called under any circumstances
            mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
