import os
import sys
import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

venv_site = os.path.join(BASE_DIR, ".venv", "lib", "python3.13", "site-packages")
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.append(venv_site)

from werkzeug.security import generate_password_hash, check_password_hash
import backend.config as config

TEST_DB_PATH = os.path.join(BASE_DIR, "test_rgukt_verification.db")
config.DATABASE_URL = ""
config.DATABASE = TEST_DB_PATH
config.SECRET_KEY = "test-rgukt-secret-key-789"
config.COLLEGE_DOMAIN = "@rguktong.ac.in"
config.OTP_REQUEST_COOLDOWN_SECONDS = 60
config.OTP_MAX_ATTEMPTS = 5

os.environ["TESTING"] = "1"
from app import create_app
from backend.database.db import get_db_connection
from backend.database.queries import init_database
from backend.services.auth_service import hash_reset_token


class TestRGUKTEmailVerificationWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.DATABASE_URL = ""
        config.DATABASE = TEST_DB_PATH
        config.COLLEGE_DOMAIN = "@rguktong.ac.in"
        config.OTP_REQUEST_COOLDOWN_SECONDS = 60
        config.OTP_MAX_ATTEMPTS = 5

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

    def setUp(self):
        with self.client.session_transaction() as sess:
            sess.clear()
        conn = get_db_connection()
        conn.execute("DELETE FROM registration_otps")
        conn.execute("DELETE FROM password_reset_otps")
        conn.execute("DELETE FROM students")
        conn.execute("DELETE FROM admin")
        conn.commit()
        conn.close()

    # -------------------------------------------------------------------------
    # 1. Valid @rguktong.ac.in email accepted
    # -------------------------------------------------------------------------
    def test_01_valid_rgukt_email_accepted(self):
        """1. Valid @rguktong.ac.in email passes validation and initiates OTP flow."""
        with patch("backend.routes.rushmitha.register.secrets.randbelow", return_value=123456):
            res = self.client.post("/register", data={
                "name": "Kishore Kumar",
                "id_no": "O210001",
                "email": "o210001@rguktong.ac.in",
                "phone": "9876543210",
                "hostel": "BH-1",
                "room": "204",
                "password": "Password@123",
                "confirm_password": "Password@123"
            }, follow_redirects=False)

            self.assertEqual(res.status_code, 302)
            loc = res.headers.get("Location", "")
            self.assertTrue("/verify-registration-otp" in loc or "/verify_registration_otp" in loc)

            # Verify OTP record in database
            conn = get_db_connection()
            otp_row = conn.execute("SELECT * FROM registration_otps WHERE email = ?", ("o210001@rguktong.ac.in",)).fetchone()
            conn.close()
            self.assertIsNotNone(otp_row)
            self.assertEqual(otp_row["otp_hash"], hash_reset_token("123456"))

    # -------------------------------------------------------------------------
    # 2. Gmail address rejected
    # -------------------------------------------------------------------------
    def test_02_gmail_address_rejected(self):
        """2. Gmail address is rejected with clear domain error and no OTP generated."""
        res = self.client.post("/register", data={
            "name": "Kishore Kumar",
            "id_no": "O210001",
            "email": "o210001@gmail.com",
            "phone": "9876543210",
            "hostel": "BH-1",
            "room": "204",
            "password": "Password@123",
            "confirm_password": "Password@123"
        }, follow_redirects=True)

        html = res.get_data(as_text=True)
        self.assertIn("Only RGUKT Ongole college email addresses ending in @rguktong.ac.in are allowed", html)

        conn = get_db_connection()
        count = conn.execute("SELECT count(*) as cnt FROM registration_otps").fetchone()["cnt"]
        conn.close()
        self.assertEqual(count, 0)

    # -------------------------------------------------------------------------
    # 3. Other domains rejected (Yahoo, Outlook, personal)
    # -------------------------------------------------------------------------
    def test_03_other_domains_rejected(self):
        """3. Yahoo, Outlook, and other non-RGUKT domains are strictly rejected."""
        domains = ["o210001@yahoo.com", "o210001@outlook.com", "o210001@somedomain.org", "o210001@rgukt.ac.in"]
        for domain_email in domains:
            res = self.client.post("/register", data={
                "name": "Test Student",
                "id_no": "O210001",
                "email": domain_email,
                "password": "Password@123",
                "confirm_password": "Password@123"
            }, follow_redirects=True)
            html = res.get_data(as_text=True)
            self.assertIn("Only RGUKT Ongole college email addresses ending in @rguktong.ac.in are allowed", html)

        conn = get_db_connection()
        count = conn.execute("SELECT count(*) as cnt FROM registration_otps").fetchone()["cnt"]
        conn.close()
        self.assertEqual(count, 0)

    # -------------------------------------------------------------------------
    # 4. OTP successfully sent via email service
    # -------------------------------------------------------------------------
    def test_04_otp_successfully_sent(self):
        """4. OTP is dispatched to student's email using the existing email service."""
        with patch("backend.routes.rushmitha.register.send_registration_otp_email") as mock_email:
            with patch("backend.routes.rushmitha.register.secrets.randbelow", return_value=789123):
                res = self.client.post("/register", data={
                    "name": "Kishore Kumar",
                    "id_no": "O210001",
                    "email": "o210001@rguktong.ac.in",
                    "password": "Password@123",
                    "confirm_password": "Password@123"
                })
                self.assertEqual(res.status_code, 302)
                mock_email.assert_called_once_with("o210001@rguktong.ac.in", "789123", expiry_minutes=5)

    # -------------------------------------------------------------------------
    # 5. Correct OTP accepted
    # -------------------------------------------------------------------------
    def test_05_correct_otp_accepted(self):
        """5. Submitting the exact correct 6-digit OTP verifies successfully and completes registration."""
        with patch("backend.routes.rushmitha.register.secrets.randbelow", return_value=654321):
            self.client.post("/register", data={
                "name": "Kishore Kumar",
                "id_no": "O210001",
                "email": "o210001@rguktong.ac.in",
                "phone": "9876543210",
                "hostel": "BH-1",
                "room": "204",
                "password": "Password@123",
                "confirm_password": "Password@123"
            })

        res = self.client.post("/verify-registration-otp", data={"otp": "654321"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Registration Successful and college email verified", html)

        # Check student account created
        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE id_no = ?", ("O210001",)).fetchone()
        conn.close()
        self.assertIsNotNone(student)
        self.assertEqual(student["email"], "o210001@rguktong.ac.in")
        self.assertEqual(student["is_verified"], 1)

    # -------------------------------------------------------------------------
    # 6. Incorrect OTP rejected
    # -------------------------------------------------------------------------
    def test_06_incorrect_otp_rejected(self):
        """6. Incorrect OTP is rejected with user-friendly error and attempt counter increments."""
        with patch("backend.routes.rushmitha.register.secrets.randbelow", return_value=123456):
            self.client.post("/register", data={
                "name": "Kishore Kumar",
                "id_no": "O210001",
                "email": "o210001@rguktong.ac.in",
                "password": "Password@123",
                "confirm_password": "Password@123"
            })

        res = self.client.post("/verify-registration-otp", data={"otp": "999999"}, follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertIn("Incorrect verification code", html)

        # Check attempts in database
        conn = get_db_connection()
        row = conn.execute("SELECT attempts FROM registration_otps WHERE id_no = ?", ("O210001",)).fetchone()
        student = conn.execute("SELECT 1 FROM students WHERE id_no = ?", ("O210001",)).fetchone()
        conn.close()
        self.assertEqual(row["attempts"], 1)
        self.assertIsNone(student, "Account must not be created on incorrect OTP")

    # -------------------------------------------------------------------------
    # 7. Expired OTP rejected
    # -------------------------------------------------------------------------
    def test_07_expired_otp_rejected(self):
        """7. OTP that has exceeded 5 minutes expiry is rejected."""
        with patch("backend.routes.rushmitha.register.secrets.randbelow", return_value=123456):
            self.client.post("/register", data={
                "name": "Kishore Kumar",
                "id_no": "O210001",
                "email": "o210001@rguktong.ac.in",
                "password": "Password@123",
                "confirm_password": "Password@123"
            })

        # Set expires_at to 10 minutes in the past
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        conn = get_db_connection()
        conn.execute("UPDATE registration_otps SET expires_at = ? WHERE id_no = ?", (past_time, "O210001"))
        conn.commit()
        conn.close()

        res = self.client.post("/verify-registration-otp", data={"otp": "123456"}, follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertIn("Verification code has expired", html)

        # Confirm no student account created
        conn = get_db_connection()
        student = conn.execute("SELECT 1 FROM students WHERE id_no = ?", ("O210001",)).fetchone()
        conn.close()
        self.assertIsNone(student)

    # -------------------------------------------------------------------------
    # 8. OTP reuse prevented
    # -------------------------------------------------------------------------
    def test_08_otp_reuse_prevented(self):
        """8. Once an OTP is used successfully, it cannot be reused."""
        with patch("backend.routes.rushmitha.register.secrets.randbelow", return_value=123456):
            self.client.post("/register", data={
                "name": "Kishore Kumar",
                "id_no": "O210001",
                "email": "o210001@rguktong.ac.in",
                "password": "Password@123",
                "confirm_password": "Password@123"
            })

        # Verify once -> Account created, OTP record cleaned up
        res1 = self.client.post("/verify-registration-otp", data={"otp": "123456"}, follow_redirects=True)
        self.assertIn("Registration Successful", res1.get_data(as_text=True))

        # Attempt to reuse the same OTP
        res2 = self.client.post("/verify-registration-otp", data={"otp": "123456"}, follow_redirects=True)
        self.assertNotIn("Registration Successful and college email verified", res2.get_data(as_text=True))

    # -------------------------------------------------------------------------
    # 9. More than 5 incorrect attempts blocked
    # -------------------------------------------------------------------------
    def test_09_more_than_5_incorrect_attempts_blocked(self):
        """9. After 5 incorrect attempts, OTP session is blocked and purged."""
        with patch("backend.routes.rushmitha.register.secrets.randbelow", return_value=123456):
            self.client.post("/register", data={
                "name": "Kishore Kumar",
                "id_no": "O210001",
                "email": "o210001@rguktong.ac.in",
                "password": "Password@123",
                "confirm_password": "Password@123"
            })

        # Submit 4 wrong attempts
        for i in range(4):
            res = self.client.post("/verify-registration-otp", data={"otp": f"00000{i}"}, follow_redirects=True)
            self.assertIn("attempt(s) remaining", res.get_data(as_text=True))

        # 5th wrong attempt triggers lockout
        res5 = self.client.post("/verify-registration-otp", data={"otp": "000009"}, follow_redirects=True)
        html5 = res5.get_data(as_text=True)
        self.assertIn("Too many incorrect attempts", html5)

        # Confirm OTP was purged from database
        conn = get_db_connection()
        otp_row = conn.execute("SELECT * FROM registration_otps WHERE id_no = ?", ("O210001",)).fetchone()
        student = conn.execute("SELECT 1 FROM students WHERE id_no = ?", ("O210001",)).fetchone()
        conn.close()
        self.assertIsNone(otp_row)
        self.assertIsNone(student)

    # -------------------------------------------------------------------------
    # 10. Resend OTP invalidates previous OTP
    # -------------------------------------------------------------------------
    def test_10_resend_otp_invalidates_previous_otp(self):
        """10. Resending an OTP generates a new OTP and completely invalidates the previous OTP."""
        with patch("backend.routes.rushmitha.register.secrets.randbelow", return_value=111111):
            self.client.post("/register", data={
                "name": "Kishore Kumar",
                "id_no": "O210001",
                "email": "o210001@rguktong.ac.in",
                "password": "Password@123",
                "confirm_password": "Password@123"
            })

        # Resend OTP
        with patch("backend.routes.rushmitha.register.secrets.randbelow", return_value=222222):
            res_resend = self.client.post("/resend-registration-otp", follow_redirects=True)
            self.assertEqual(res_resend.status_code, 200)

        # Attempt to use old OTP 111111 -> Must be rejected
        res_old = self.client.post("/verify-registration-otp", data={"otp": "111111"}, follow_redirects=True)
        self.assertIn("Incorrect verification code", res_old.get_data(as_text=True))

        # Use new OTP 222222 -> Must succeed
        res_new = self.client.post("/verify-registration-otp", data={"otp": "222222"}, follow_redirects=True)
        self.assertIn("Registration Successful and college email verified", res_new.get_data(as_text=True))

    # -------------------------------------------------------------------------
    # 11. Duplicate email rejected
    # -------------------------------------------------------------------------
    def test_11_duplicate_email_rejected(self):
        """11. Registration with an already registered college email is rejected."""
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO students (name, id_no, email, phone, hostel, room_no, password, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            ("Existing Student", "O210099", "o210001@rguktong.ac.in", "9999999999", "BH-1", "101", generate_password_hash("pw"))
        )
        conn.commit()
        conn.close()

        res = self.client.post("/register", data={
            "name": "Another Student",
            "id_no": "O210001",
            "email": "o210001@rguktong.ac.in",
            "password": "Password@123",
            "confirm_password": "Password@123"
        }, follow_redirects=True)

        self.assertIn("Email Already Exists", res.get_data(as_text=True))

    # -------------------------------------------------------------------------
    # 12. Duplicate student ID rejected
    # -------------------------------------------------------------------------
    def test_12_duplicate_student_id_rejected(self):
        """12. Registration with an already registered ID number is rejected."""
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO students (name, id_no, email, phone, hostel, room_no, password, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            ("Existing Student", "O210001", "o210001@rguktong.ac.in", "9999999999", "BH-1", "101", generate_password_hash("pw"))
        )
        conn.commit()
        conn.close()

        res = self.client.post("/register", data={
            "name": "Different Student",
            "id_no": "O210001",
            "email": "o210001@rguktong.ac.in",
            "password": "Password@123",
            "confirm_password": "Password@123"
        }, follow_redirects=True)

        self.assertIn("ID Number Already Exists", res.get_data(as_text=True))

    # -------------------------------------------------------------------------
    # 13. Account not created before OTP verification
    # -------------------------------------------------------------------------
    def test_13_account_not_created_before_otp_verification(self):
        """13. Initial registration submission does NOT create a student account in database."""
        with patch("backend.routes.rushmitha.register.secrets.randbelow", return_value=123456):
            self.client.post("/register", data={
                "name": "Pending Student",
                "id_no": "O210003",
                "email": "o210003@rguktong.ac.in",
                "password": "Password@123",
                "confirm_password": "Password@123"
            })

        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE id_no = ?", ("O210003",)).fetchone()
        conn.close()
        self.assertIsNone(student, "Account must NOT exist in students table before verification")

    # -------------------------------------------------------------------------
    # 14. Account created only after successful OTP verification
    # -------------------------------------------------------------------------
    def test_14_account_created_only_after_successful_verification(self):
        """14. Student account is created in database only after successful OTP submission."""
        with patch("backend.routes.rushmitha.register.secrets.randbelow", return_value=333444):
            self.client.post("/register", data={
                "name": "Verified Student",
                "id_no": "O210004",
                "email": "o210004@rguktong.ac.in",
                "phone": "9876543210",
                "hostel": "BH-2",
                "room": "105",
                "password": "SecurePassword123",
                "confirm_password": "SecurePassword123"
            })

        # Still 0 before verify
        conn = get_db_connection()
        count_before = conn.execute("SELECT count(*) as cnt FROM students WHERE id_no = ?", ("O210004",)).fetchone()["cnt"]
        conn.close()
        self.assertEqual(count_before, 0)

        # Submit OTP
        self.client.post("/verify-registration-otp", data={"otp": "333444"}, follow_redirects=True)

        # Now exactly 1 in students table
        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE id_no = ?", ("O210004",)).fetchone()
        conn.close()
        self.assertIsNotNone(student)
        self.assertEqual(student["name"], "Verified Student")
        self.assertEqual(student["is_verified"], 1)
        self.assertTrue(check_password_hash(student["password"], "SecurePassword123"))

    # -------------------------------------------------------------------------
    # 15. Unverified account cannot log in
    # -------------------------------------------------------------------------
    def test_15_unverified_account_cannot_login(self):
        """15. Student accounts with is_verified=0 are blocked from logging in."""
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO students (name, id_no, email, phone, hostel, room_no, password, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            ("Unverified User", "O210005", "o210005@rguktong.ac.in", "9999999999", "BH-1", "101", generate_password_hash("Password123"))
        )
        conn.commit()
        conn.close()

        res = self.client.post("/login", data={
            "id_no": "O210005",
            "password": "Password123"
        }, follow_redirects=True)

        html = res.get_data(as_text=True)
        self.assertIn("Your account email is not verified", html)

        # Check session
        with self.client.session_transaction() as sess:
            self.assertNotIn("student_id", sess)

    # -------------------------------------------------------------------------
    # 16. Verified student can log in
    # -------------------------------------------------------------------------
    def test_16_verified_student_can_login(self):
        """16. Verified student can log in and access protected session."""
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO students (name, id_no, email, phone, hostel, room_no, password, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            ("Verified User", "O210006", "o210006@rguktong.ac.in", "9999999999", "BH-1", "101", generate_password_hash("Password123"))
        )
        conn.commit()
        conn.close()

        res = self.client.post("/login", data={
            "id_no": "O210006",
            "password": "Password123"
        }, follow_redirects=True)

        self.assertIn("Login Successful", res.get_data(as_text=True))
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("id_no"), "O210006")

    # -------------------------------------------------------------------------
    # 17. Existing Forgot Password functionality still works
    # -------------------------------------------------------------------------
    def test_17_existing_forgot_password_still_works(self):
        """17. Password reset OTP workflow continues to function perfectly."""
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO students (name, id_no, email, phone, hostel, room_no, password, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            ("Reset User", "O210007", "o210007@rguktong.ac.in", "9999999999", "BH-1", "101", generate_password_hash("OldPassword123"))
        )
        conn.commit()
        conn.close()

        # Request reset OTP
        with patch("backend.routes.deepthi.forgot_password.secrets.randbelow", return_value=888999):
            res_fp = self.client.post("/forgot_password", data={"email": "o210007@rguktong.ac.in"}, follow_redirects=True)
            self.assertIn("OTP sent successfully", res_fp.get_data(as_text=True))

        # Verify reset OTP
        res_vr = self.client.post("/verify-reset-otp", data={"otp": "888999"}, follow_redirects=True)
        self.assertEqual(res_vr.status_code, 200)

        # Reset password
        res_rp = self.client.post("/reset_password", data={
            "password": "NewSecurePassword123",
            "confirm_password": "NewSecurePassword123"
        }, follow_redirects=True)
        self.assertIn("Password reset successful", res_rp.get_data(as_text=True))

        # Log in with new password
        res_login = self.client.post("/login", data={
            "id_no": "O210007",
            "password": "NewSecurePassword123"
        }, follow_redirects=True)
        self.assertIn("Login Successful", res_login.get_data(as_text=True))

    # -------------------------------------------------------------------------
    # 18. Existing admin login still works
    # -------------------------------------------------------------------------
    def test_18_existing_admin_login_still_works(self):
        """18. Admin login functionality remains completely intact and operational."""
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO admin (username, password) VALUES (?, ?)",
            ("portal_admin", generate_password_hash("AdminPass999!"))
        )
        conn.commit()
        conn.close()

        res = self.client.post("/admin_login", data={
            "username": "portal_admin",
            "password": "AdminPass999!"
        }, follow_redirects=True)

        self.assertIn("Admin Login Successful", res.get_data(as_text=True))
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("admin"), "portal_admin")


if __name__ == "__main__":
    unittest.main()
