import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

venv_site = os.path.join(BASE_DIR, ".venv", "lib", "python3.13", "site-packages")
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.append(venv_site)

from werkzeug.security import generate_password_hash, check_password_hash

import config

# Force isolated SQLite test database
TEST_DB_PATH = os.path.join(BASE_DIR, "test_forgot_password.db")
config.DATABASE_URL = ""
config.DATABASE = TEST_DB_PATH
config.SECRET_KEY = "test-forgot-secret-key-123"

os.environ["TESTING"] = "1"
from app import create_app
from database.db import get_db_connection
from database.queries import init_database
from services.auth_service import hash_reset_token

class TestForgotPasswordWorkflow(unittest.TestCase):
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

        # Seed registered test student
        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO students (name, id_no, email, phone, hostel, room_no, password)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Test Student",
                "O210001",
                "o210001@rguktong.ac.in",
                "9876543210",
                "BH-1",
                "101",
                generate_password_hash("OldPassword123")
            )
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
        # Clear reset OTPs between tests
        conn = get_db_connection()
        conn.execute("DELETE FROM password_reset_otps")
        conn.commit()
        conn.close()

    def test_01_gmail_rejected(self):
        """Test 1: student@gmail.com must be rejected with domain error and no OTP generated."""
        res = self.client.post("/forgot_password", data={"email": "student@gmail.com"})
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Please enter your registered RGUKT college email address.", html)

        # Confirm no OTP was created
        conn = get_db_connection()
        count = conn.execute("SELECT count(*) as cnt FROM password_reset_otps").fetchone()["cnt"]
        conn.close()
        self.assertEqual(count, 0, "No OTP should be generated for Gmail address")

    def test_02_yahoo_rejected(self):
        """Test 2: student@yahoo.com must be rejected with domain error and no OTP generated."""
        res = self.client.post("/forgot_password", data={"email": "student@yahoo.com"})
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Please enter your registered RGUKT college email address.", html)

        conn = get_db_connection()
        count = conn.execute("SELECT count(*) as cnt FROM password_reset_otps").fetchone()["cnt"]
        conn.close()
        self.assertEqual(count, 0)

    def test_03_outlook_rejected(self):
        """Test 3: student@outlook.com must be rejected with domain error and no OTP generated."""
        res = self.client.post("/forgot_password", data={"email": "student@outlook.com"})
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Please enter your registered RGUKT college email address.", html)

        conn = get_db_connection()
        count = conn.execute("SELECT count(*) as cnt FROM password_reset_otps").fetchone()["cnt"]
        conn.close()
        self.assertEqual(count, 0)

    def test_04_unregistered_college_email(self):
        """Test 4: unknown@rguktong.ac.in (valid domain, account not found) must show differentiated error."""
        with self.client as c:
            res = c.post("/forgot_password", data={"email": "unknown@rguktong.ac.in"})
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn("No account found with this college email address. Please check your email or create a student account.", html)
            self.assertNotIn("If an account exists for that email", html)

            # Confirm no reset session was created
            from flask import session
            self.assertNotIn("reset_student_id", session)

            # Confirm no OTP was stored
            conn = get_db_connection()
            count = conn.execute("SELECT count(*) as cnt FROM password_reset_otps").fetchone()["cnt"]
            conn.close()
            self.assertEqual(count, 0, "No OTP should be created for non-existent account")

    def test_05_registered_college_email_success(self):
        """Test 5: Registered college email generates OTP, sets session, and redirects to verify OTP."""
        with self.client as c:
            res = c.post("/forgot_password", data={"email": "o210001@rguktong.ac.in"}, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn("OTP sent successfully to your registered college email.", html)
            self.assertIn("Verify OTP Code", html)

            from flask import session
            self.assertEqual(session.get("reset_email"), "o210001@rguktong.ac.in")
            self.assertIsNotNone(session.get("reset_student_id"))

            # Verify OTP row in database
            conn = get_db_connection()
            otp_row = conn.execute(
                "SELECT * FROM password_reset_otps WHERE student_id=?",
                (session["reset_student_id"],)
            ).fetchone()
            conn.close()
            self.assertIsNotNone(otp_row)
            self.assertEqual(len(otp_row["otp_hash"]), 64)  # SHA-256 hash
            self.assertEqual(otp_row["attempts"], 0)
            self.assertEqual(otp_row["verified"], 0)

    def test_06_uppercase_domain_case_insensitivity(self):
        """Test 6: Uppercase domain O210001@RGUKTONG.AC.IN is accepted case-insensitively."""
        with self.client as c:
            res = c.post("/forgot_password", data={"email": "O210001@RGUKTONG.AC.IN"}, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn("OTP sent successfully to your registered college email.", html)

            conn = get_db_connection()
            count = conn.execute("SELECT count(*) as cnt FROM password_reset_otps").fetchone()["cnt"]
            conn.close()
            self.assertEqual(count, 1)

    def test_07_leading_trailing_whitespace(self):
        """Test 7: Leading/trailing whitespace is properly stripped."""
        with self.client as c:
            res = c.post("/forgot_password", data={"email": "   o210001@rguktong.ac.in   "}, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn("OTP sent successfully to your registered college email.", html)

    def test_08_empty_field(self):
        """Test 8: Empty field is rejected with required error and no OTP."""
        res = self.client.post("/forgot_password", data={"email": "   "})
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Email address is required.", html)

        conn = get_db_connection()
        count = conn.execute("SELECT count(*) as cnt FROM password_reset_otps").fetchone()["cnt"]
        conn.close()
        self.assertEqual(count, 0)

    def test_09_invalid_email_syntax(self):
        """Test 9: Invalid email syntax (student@) is rejected."""
        res = self.client.post("/forgot_password", data={"email": "student@"})
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Please enter a valid email address.", html)

        conn = get_db_connection()
        count = conn.execute("SELECT count(*) as cnt FROM password_reset_otps").fetchone()["cnt"]
        conn.close()
        self.assertEqual(count, 0)

    def test_10_full_end_to_end_password_reset_flow(self):
        """Test 10: Complete flow: Forgot Password -> OTP generated -> Verify OTP -> Reset Password -> Login with new password."""
        with self.client as c:
            # 1. Request OTP
            res = c.post("/forgot_password", data={"email": "o210001@rguktong.ac.in"}, follow_redirects=True)
            self.assertEqual(res.status_code, 200)

            # Retrieve student ID and plain OTP by matching 6-digit hashes
            from flask import session
            student_id = session["reset_student_id"]

            conn = get_db_connection()
            otp_row = conn.execute(
                "SELECT * FROM password_reset_otps WHERE student_id=?",
                (student_id,)
            ).fetchone()
            conn.close()

            # Find matching OTP
            target_hash = otp_row["otp_hash"]
            matched_otp = None
            for candidate in range(1000000):
                c_str = f"{candidate:06d}"
                if hash_reset_token(c_str) == target_hash:
                    matched_otp = c_str
                    break

            self.assertIsNotNone(matched_otp, "Should find the generated 6-digit OTP")

            # 2. Verify OTP
            verify_res = c.post("/verify-reset-otp", data={"otp": matched_otp}, follow_redirects=True)
            self.assertEqual(verify_res.status_code, 200)
            self.assertIn("Create New Password", verify_res.get_data(as_text=True))
            self.assertTrue(session.get("reset_verified"))

            # 3. Reset Password to NewSecurePassword999
            reset_res = c.post(
                "/reset-password",
                data={
                    "password": "NewSecurePassword999",
                    "confirm_password": "NewSecurePassword999"
                },
                follow_redirects=True
            )
            self.assertEqual(reset_res.status_code, 200)
            reset_html = reset_res.get_data(as_text=True)
            self.assertIn("Password reset successfully. You can now log in.", reset_html)

            # 4. Verify password in DB was updated
            conn = get_db_connection()
            student = conn.execute("SELECT password FROM students WHERE id=?", (student_id,)).fetchone()
            conn.close()
            self.assertTrue(check_password_hash(student["password"], "NewSecurePassword999"))

            # 5. Verify successful login with new password
            login_res = c.post(
                "/login",
                data={
                    "id_no": "O210001",
                    "password": "NewSecurePassword999"
                },
                follow_redirects=True
            )
            self.assertEqual(login_res.status_code, 200)
            self.assertIn("Login Successful.", login_res.get_data(as_text=True))
            self.assertEqual(session.get("student_id"), student_id)

    def test_11_frontend_template_and_js_validation(self):
        """Test 11: Verify template markup, helper text, error container, and JS client validation."""
        res = self.client.get("/forgot_password")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Form elements
        self.assertIn('id="forgotPasswordForm"', html)
        self.assertIn('novalidate', html)
        self.assertIn('placeholder="e.g. oxxxxxx@rguktong.ac.in"', html)
        self.assertIn('id="emailHelp"', html)
        self.assertIn('Use your registered RGUKT college email address.', html)
        self.assertIn('id="emailClientError"', html)
        self.assertIn('id="submitBtn"', html)

        # JS client script
        js_path = os.path.join(BASE_DIR, "static", "js", "deepthi", "forgot_password.js")
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn("@rguktong.ac.in", js)
        self.assertIn("Please enter your registered RGUKT college email address.", js)
        self.assertIn("validateEmailValue", js)
        self.assertIn("emailClientError", js)

    def test_12_otp_input_attributes_and_no_masking(self):
        """Test 12: Verify OTP input has type='text', id='otp', not password masked."""
        with self.client as c:
            # Set reset session
            with c.session_transaction() as sess:
                sess["reset_student_id"] = 1
                sess["reset_email"] = "o210001@rguktong.ac.in"

            res = c.get("/verify-reset-otp")
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)

            self.assertIn('type="text"', html)
            self.assertIn('id="otp"', html)
            self.assertIn('class="otp-input-control"', html)
            self.assertIn('maxlength="6"', html)
            self.assertIn('inputmode="numeric"', html)
            self.assertNotIn('type="password"', html)

    def test_13_otp_input_css_styles_both_themes(self):
        """Test 13: Verify OTP CSS definitions for readable text and dark theme overrides."""
        css_path = os.path.join(BASE_DIR, "static", "css", "deepthi", "verify_reset_otp.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Check font, color, text-fill-color, background, placeholder
        self.assertIn(".otp-input-control", css)
        self.assertIn("color: var(--text-heading)", css)
        self.assertIn("-webkit-text-fill-color: var(--text-heading)", css)
        self.assertIn("background-color: var(--bg-input", css)
        self.assertIn(".otp-input-control::placeholder", css)
        self.assertIn("[data-theme=\"dark\"] .otp-input-control", css)
        self.assertIn("[data-theme=\"dark\"] .otp-verify-card", css)

        # Check style.css theme dark mappings
        style_css_path = os.path.join(BASE_DIR, "static", "css", "style.css")
        with open(style_css_path, "r", encoding="utf-8") as f:
            style_css = f.read()

        self.assertIn(".otp-verify-card", style_css)
        self.assertIn(".otp-input-control", style_css)
        self.assertIn("--text-primary: #0f172a", style_css)
        self.assertIn("--text-primary: #f8fafc", style_css)

    def test_14_invalid_otp_preserves_value_and_displays_error(self):
        """Test 14: Wrong OTP displays error and preserves entered value in input."""
        with self.client as c:
            # First request OTP
            c.post("/forgot_password", data={"email": "o210001@rguktong.ac.in"})

            # Post wrong OTP
            res = c.post("/verify-reset-otp", data={"otp": "893472"}, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)

            self.assertIn("Incorrect OTP. Please try again.", html)
            self.assertIn('value="893472"', html)

    def test_15_invalid_format_otp_preserves_value(self):
        """Test 15: Invalid length/format OTP preserves value and shows validation message."""
        with self.client as c:
            c.post("/forgot_password", data={"email": "o210001@rguktong.ac.in"})

            res = c.post("/verify-reset-otp", data={"otp": "12345"}, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)

            self.assertIn("Enter a valid 6-digit OTP.", html)
            self.assertIn('value="12345"', html)

    def test_16_recovery_email_input_styling_and_contrast(self):
        """Test 16: Verify recovery email input has dark text on light background in both themes."""
        # 1. Template markup
        res = self.client.get("/forgot_password")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('class="recovery-input"', html)
        self.assertIn('type="email"', html)
        self.assertIn('id="email"', html)

        # 2. Value retention on validation error
        err_res = self.client.post("/forgot_password", data={"email": "0221168@rguktong.ac.in"})
        self.assertEqual(err_res.status_code, 200)
        err_html = err_res.get_data(as_text=True)
        self.assertIn('value="0221168@rguktong.ac.in"', err_html)

        # 3. Component CSS: forgot_password.css
        css_path = os.path.join(BASE_DIR, "static", "css", "deepthi", "forgot_password.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn(".recovery-input", css)
        self.assertIn("-webkit-text-fill-color: var(--input-light-text, #0f172a)", css)
        self.assertIn("background-color: var(--input-light-bg, #ffffff)", css)
        self.assertIn(".recovery-input::placeholder", css)
        self.assertIn("[data-theme=\"dark\"] .recovery-input", css)
        self.assertIn("[data-theme=\"dark\"] .recovery-input::placeholder", css)

        # 4. Global CSS: style.css
        style_path = os.path.join(BASE_DIR, "static", "css", "style.css")
        with open(style_path, "r", encoding="utf-8") as f:
            style = f.read()

        self.assertIn("--input-light-bg: #ffffff", style)
        self.assertIn("--input-light-text: #0f172a", style)
        self.assertIn("--input-light-placeholder: #64748b", style)
        self.assertIn(".recovery-input", style)
        self.assertIn("[data-theme=\"dark\"] .recovery-input", style)
        self.assertIn(".recovery-input:-webkit-autofill", style)

if __name__ == "__main__":
    unittest.main()


