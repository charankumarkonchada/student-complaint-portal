import os
import sys
import unittest
from unittest.mock import patch, MagicMock

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
import smtplib

TEST_REG_DB = os.path.join(BASE_DIR, "test_regression_email.db")
config.DATABASE_URL = ""
config.DATABASE = TEST_REG_DB
config.SECRET_KEY = "test-regression-secret-key"

os.environ["TESTING"] = "1"
from app import create_app
from database.db import get_db_connection
from database.queries import init_database
from services.email_service import (
    send_email,
    send_otp_email,
    send_complaint_status_email,
    send_common_issue_status_email,
    send_common_issue_broadcast_emails,
    send_complaint_submitted_email,
    is_test_environment,
    is_smtp_mocked,
)
from services.common_issue_service import (
    create_common_issue,
    update_common_issue_once,
)


class TestEmailIsolationRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.DATABASE_URL = ""
        config.DATABASE = TEST_REG_DB
        if os.path.exists(TEST_REG_DB):
            try:
                os.remove(TEST_REG_DB)
            except Exception:
                pass
        init_database()
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_REG_DB):
            try:
                os.remove(TEST_REG_DB)
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
        conn.execute(
            """
            INSERT INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (1, 'Test Student', 'O200001', 'o200001@rguktong.ac.in', '9876543210', 'Hostel Block A', '101', 'hash')
            """
        )
        conn.commit()
        conn.close()

    # =========================================================================
    # REQUIREMENT 9.A: When TESTING mode is enabled, verify zero real SMTP traffic
    # =========================================================================
    def test_a1_send_email_suppressed_in_testing_mode_without_smtp_connection(self):
        """Proves send_email() suppresses sending and never invokes smtplib.SMTP when unmocked."""
        with patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", True), \
             patch.object(config, "SMTP_USERNAME", "mailer@example.com"), \
             patch.object(config, "SMTP_PASSWORD", "secret123"), \
             patch.object(config, "MAIL_FROM", "mailer@example.com"):

            # Spy on smtplib.SMTP: if called, record invocation
            smtp_called = []
            real_smtp_cls = smtplib.SMTP

            def spy_smtp(*args, **kwargs):
                smtp_called.append(args)
                raise AssertionError("smtplib.SMTP was invoked during automated tests!")

            with patch.object(smtplib, "SMTP", side_effect=spy_smtp):
                # Ensure is_smtp_mocked returns False so we test the unmocked safety branch
                with patch("services.email_service.is_smtp_mocked", return_value=False):
                    res = send_email("o200001@rguktong.ac.in", "Test Subject", "Test Body")
                    self.assertFalse(res, "send_email must return False when suppressed in test mode")
                    self.assertEqual(len(smtp_called), 0, "No SMTP instance should ever be created")

    def test_a2_send_otp_email_suppressed_in_testing_mode_without_smtp_connection(self):
        """Proves send_otp_email() suppresses sending and never invokes smtplib.SMTP when unmocked."""
        with patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", True), \
             patch.object(config, "SMTP_USERNAME", "mailer@example.com"), \
             patch.object(config, "SMTP_PASSWORD", "secret123"), \
             patch.object(config, "MAIL_FROM", "mailer@example.com"):

            smtp_called = []

            def spy_smtp(*args, **kwargs):
                smtp_called.append(args)
                raise AssertionError("smtplib.SMTP was invoked during send_otp_email in test mode!")

            with patch.object(smtplib, "SMTP", side_effect=spy_smtp):
                with patch("services.email_service.is_smtp_mocked", return_value=False):
                    # Should return None safely and NOT raise or call SMTP
                    send_otp_email("o200001@rguktong.ac.in", "123456")
                    self.assertEqual(len(smtp_called), 0, "No SMTP instance should ever be created for OTP")

    def test_a3_complaint_submission_cannot_trigger_real_smtp(self):
        """Proves complaint submission creates DB records without initiating any real SMTP connection."""
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["role"] = "student"
            sess["name"] = "Test Student"
            sess["hostel"] = "Hostel Block A"

        smtp_called = []

        def spy_smtp(*args, **kwargs):
            smtp_called.append(args)
            raise AssertionError("smtplib.SMTP was invoked during complaint submission!")

        with patch.object(smtplib, "SMTP", side_effect=spy_smtp):
            with patch("services.email_service.is_smtp_mocked", return_value=False):
                res = self.client.post("/add_complaint", data={
                    "category": "Plumbing",
                    "priority": "Medium",
                    "title": "Leaking tap in bathroom",
                    "description": "Continuous water drip from the main tap."
                }, follow_redirects=True)
                self.assertEqual(res.status_code, 200)
                self.assertEqual(len(smtp_called), 0, "Complaint submission must not cause real SMTP traffic")

                # Verify complaint exists in database
                conn = get_db_connection()
                complaint = conn.execute(
                    "SELECT * FROM complaints WHERE student_id = 1 AND title = 'Leaking tap in bathroom'"
                ).fetchone()
                conn.close()
                self.assertIsNotNone(complaint, "Complaint must be successfully recorded in the database")

    def test_a4_common_issue_broadcast_cannot_trigger_real_smtp(self):
        """Proves Common Issue status updates and broadcasts do not initiate any real SMTP connections."""
        conn = get_db_connection()
        ci_id = create_common_issue(
            title="Block A Main Valve Failure",
            category="Plumbing",
            hostel="Hostel Block A",
            location_details="Block A washrooms",
            description="Water valve broken",
            priority="High",
            created_by="Admin",
            conn=conn
        )
        conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status, common_issue_id)
            VALUES (1, 'Plumbing', 'Water outage', 'No water', 'High', 'Pending', ?)
            """,
            (ci_id,)
        )
        conn.commit()
        conn.close()

        smtp_called = []

        def spy_smtp(*args, **kwargs):
            smtp_called.append(args)
            raise AssertionError("smtplib.SMTP was invoked during Common Issue broadcast!")

        with patch.object(smtplib, "SMTP", side_effect=spy_smtp):
            with patch("services.email_service.is_smtp_mocked", return_value=False):
                affected = update_common_issue_once(
                    common_issue_id=ci_id,
                    status="Resolved",
                    remarks="Fixed pump",
                    assigned_to="Plumber team"
                )
                self.assertEqual(affected, 1)
                self.assertEqual(len(smtp_called), 0, "Common Issue broadcast must not cause real SMTP traffic")

    # =========================================================================
    # REQUIREMENT 9.B: When testing email functionality, mocked SMTP works
    # =========================================================================
    def test_b1_mocked_smtp_called_correctly_for_send_email(self):
        """Proves that when smtplib.SMTP is mocked, email content/headers/recipient are verified."""
        with patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", True), \
             patch.object(config, "SMTP_USERNAME", "mailer@example.com"), \
             patch.object(config, "SMTP_PASSWORD", "secret123"), \
             patch.object(config, "MAIL_FROM", "mailer@example.com"), \
             patch.object(config, "SMTP_USE_TLS", True):
            with patch("smtplib.SMTP") as mock_smtp_cls:
                mock_instance = MagicMock()
                mock_smtp_cls.return_value.__enter__.return_value = mock_instance

                res = send_email(
                    recipient="o200001@rguktong.ac.in",
                    subject="Status Notification",
                    text_body="Your complaint is resolved.",
                    html_body="<p>Your complaint is resolved.</p>"
                )
                self.assertTrue(res)
                mock_instance.starttls.assert_called_once()
                mock_instance.login.assert_called_once_with("mailer@example.com", "secret123")
                mock_instance.send_message.assert_called_once()

                sent_msg = mock_instance.send_message.call_args[0][0]
                self.assertEqual(sent_msg["To"], "o200001@rguktong.ac.in")
                self.assertEqual(sent_msg["Subject"], "Status Notification")
                self.assertEqual(sent_msg["From"], "mailer@example.com")
                self.assertIn("Your complaint is resolved.", sent_msg.as_string())

    def test_b2_mocked_smtp_called_correctly_for_send_otp_email(self):
        """Proves that when smtplib.SMTP is mocked, OTP emails are generated and delivered to the mock."""
        with patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", True), \
             patch.object(config, "SMTP_USERNAME", "mailer@example.com"), \
             patch.object(config, "SMTP_PASSWORD", "secret123"), \
             patch.object(config, "MAIL_FROM", "mailer@example.com"), \
             patch.object(config, "SMTP_USE_TLS", True):
            with patch("smtplib.SMTP") as mock_smtp_cls:
                mock_instance = MagicMock()
                mock_smtp_cls.return_value.__enter__.return_value = mock_instance

                send_otp_email("o200001@rguktong.ac.in", "987654")

                mock_instance.starttls.assert_called_once()
                mock_instance.login.assert_called_once_with("mailer@example.com", "secret123")
                mock_instance.send_message.assert_called_once()

                sent_msg = mock_instance.send_message.call_args[0][0]
                self.assertEqual(sent_msg["To"], "o200001@rguktong.ac.in")
                self.assertIn("Password Reset OTP", sent_msg["Subject"])
                self.assertIn("987654", sent_msg.get_content())

    # =========================================================================
    # REQUIREMENT 9.C: Existing application functionality remains unchanged
    # =========================================================================
    def test_c1_production_environment_detection_preserves_email_behavior(self):
        """Proves that outside of test environments, is_test_environment() evaluates to False."""
        # Clean environment without testing flags
        env_clean = {k: v for k, v in os.environ.items() if k not in ("TESTING", "FLASK_ENV", "APP_ENV", "PYTEST_CURRENT_TEST")}
        with patch.dict(os.environ, env_clean, clear=True):
            # Outside of Flask app context
            self.assertFalse(is_test_environment(), "is_test_environment() must be False in production environment")

    def test_c2_is_smtp_mocked_detection_accuracy(self):
        """Proves is_smtp_mocked() reliably distinguishes between real smtplib and unittest.mock."""
        # Unmocked state
        with patch("services.email_service.smtplib.SMTP", smtplib.SMTP):
            self.assertFalse(is_smtp_mocked(), "Real smtplib.SMTP must not be identified as mocked")

        # Mocked state
        with patch("smtplib.SMTP") as mock_s:
            self.assertTrue(is_smtp_mocked(), "MagicMock smtplib.SMTP must be identified as mocked")


if __name__ == "__main__":
    unittest.main()
