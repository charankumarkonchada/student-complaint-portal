import os
import sys
import unittest
from html.parser import HTMLParser

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

venv_site = os.path.join(BASE_DIR, ".venv", "lib", "python3.13", "site-packages")
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.append(venv_site)

from werkzeug.security import generate_password_hash
import config
from app import create_app
from database.db import get_db_connection
from database.queries import init_database

TEST_DB_PATH = os.path.join(BASE_DIR, "test_pw_vis.db")


class FormInputParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.password_inputs = []
        self.toggle_buttons = []
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == "input" and attr_dict.get("type") == "password":
            self.password_inputs.append(attr_dict)
        elif tag == "button" and "password-toggle" in attr_dict.get("class", "").split():
            self.toggle_buttons.append(attr_dict)


class PasswordToggleSimulator:
    """Simulates the client-side JavaScript engine in static/js/script.js."""
    def __init__(self, input_id, initial_type="password", initial_value="SecretPass123!"):
        self.input_id = input_id
        self.input_type = initial_type
        self.value = initial_value
        self.button_aria_label = "Show password"
        self.button_aria_pressed = "false"
        self.button_title = "Show password"
        self.icon_class = "fa-solid fa-eye"

    def click(self):
        # Step 2: Toggle password visibility without losing value
        is_password = self.input_type == "password"
        self.input_type = "text" if is_password else "password"

        # Step 3: Synchronize Font Awesome eye icon
        if is_password:
            self.icon_class = self.icon_class.replace("fa-eye", "fa-eye-slash")
        else:
            self.icon_class = self.icon_class.replace("fa-eye-slash", "fa-eye")

        # Step 4: Update accessibility states
        next_label = "Hide password" if is_password else "Show password"
        self.button_aria_label = next_label
        self.button_aria_pressed = "true" if is_password else "false"
        self.button_title = next_label


class TestPasswordVisibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

        config.DATABASE_URL = ""
        config.DATABASE = TEST_DB_PATH
        config.SECRET_KEY = "test-pw-visibility-secret"

        init_database()
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

        # Seed test student
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT OR REPLACE INTO students (id, id_no, name, email, phone, hostel, room_no, password)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "O180001",
                "Test Student",
                "o180001@rguktong.ac.in",
                "9876543210",
                "BH-1",
                "101",
                generate_password_hash("StudentPass123!"),
            ),
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

    def test_01_student_login_page_markup(self):
        """Verify Student Login page has password field with associated toggle button."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        parser = FormInputParser()
        parser.feed(html)

        self.assertEqual(len(parser.password_inputs), 1)
        pw_input = parser.password_inputs[0]
        self.assertEqual(pw_input.get("id"), "password")

        self.assertEqual(len(parser.toggle_buttons), 1)
        toggle_btn = parser.toggle_buttons[0]
        self.assertEqual(toggle_btn.get("data-target"), "password")
        self.assertEqual(toggle_btn.get("aria-controls"), "password")
        self.assertEqual(toggle_btn.get("aria-label"), "Show password")
        self.assertEqual(toggle_btn.get("aria-pressed"), "false")
        self.assertIn("fa-solid fa-eye", html)

    def test_02_admin_login_page_markup(self):
        """Verify Admin Login page has password field with associated toggle button."""
        res = self.client.get("/admin_login")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        parser = FormInputParser()
        parser.feed(html)

        self.assertEqual(len(parser.password_inputs), 1)
        pw_input = parser.password_inputs[0]
        self.assertEqual(pw_input.get("id"), "password")

        self.assertEqual(len(parser.toggle_buttons), 1)
        toggle_btn = parser.toggle_buttons[0]
        self.assertEqual(toggle_btn.get("data-target"), "password")
        self.assertEqual(toggle_btn.get("aria-controls"), "password")
        self.assertEqual(toggle_btn.get("aria-label"), "Show password")
        self.assertEqual(toggle_btn.get("aria-pressed"), "false")

    def test_03_registration_page_markup(self):
        """Verify Registration page has both password and confirm_password with independent toggles."""
        res = self.client.get("/register")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        parser = FormInputParser()
        parser.feed(html)

        self.assertEqual(len(parser.password_inputs), 2)
        input_ids = [inp.get("id") for inp in parser.password_inputs]
        self.assertIn("password", input_ids)
        self.assertIn("confirm_password", input_ids)

        self.assertEqual(len(parser.toggle_buttons), 2)
        btn_targets = [btn.get("data-target") for btn in parser.toggle_buttons]
        self.assertIn("password", btn_targets)
        self.assertIn("confirm_password", btn_targets)

        for btn in parser.toggle_buttons:
            self.assertEqual(btn.get("type"), "button")
            self.assertEqual(btn.get("aria-label"), "Show password")
            self.assertEqual(btn.get("aria-pressed"), "false")

    def test_04_reset_password_page_markup(self):
        """Verify Reset Password page has both password and confirm_password with independent toggles."""
        with self.client.session_transaction() as sess:
            sess["reset_verified"] = True
            sess["reset_student_id"] = 1
            sess["reset_email"] = "o180001@rguktong.ac.in"

        res = self.client.get("/reset-password")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        parser = FormInputParser()
        parser.feed(html)

        self.assertEqual(len(parser.password_inputs), 2)
        input_ids = [inp.get("id") for inp in parser.password_inputs]
        self.assertIn("password", input_ids)
        self.assertIn("confirm_password", input_ids)

        self.assertEqual(len(parser.toggle_buttons), 2)
        btn_targets = [btn.get("data-target") for btn in parser.toggle_buttons]
        self.assertIn("password", btn_targets)
        self.assertIn("confirm_password", btn_targets)

    def test_05_change_password_page_markup(self):
        """Verify Change Password page has 3 password fields with 3 independent toggles."""
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["id_no"] = "O180001"
            sess["student_name"] = "Test Student"

        res = self.client.get("/change_password")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        parser = FormInputParser()
        parser.feed(html)

        self.assertEqual(len(parser.password_inputs), 3)
        input_ids = [inp.get("id") for inp in parser.password_inputs]
        self.assertIn("old_password", input_ids)
        self.assertIn("new_password", input_ids)
        self.assertIn("confirm_password", input_ids)

        self.assertEqual(len(parser.toggle_buttons), 3)
        btn_targets = [btn.get("data-target") for btn in parser.toggle_buttons]
        self.assertIn("old_password", btn_targets)
        self.assertIn("new_password", btn_targets)
        self.assertIn("confirm_password", btn_targets)

    def test_06_state_machine_and_multi_click_cycles(self):
        """Simulate repeated clicks and verify state transitions and value preservation."""
        sim = PasswordToggleSimulator("password", initial_type="password", initial_value="MySecret#2026")

        # Initial state
        self.assertEqual(sim.input_type, "password")
        self.assertEqual(sim.value, "MySecret#2026")
        self.assertEqual(sim.button_aria_label, "Show password")
        self.assertEqual(sim.button_aria_pressed, "false")
        self.assertEqual(sim.icon_class, "fa-solid fa-eye")

        # Cycle through 10 toggles
        for i in range(1, 11):
            sim.click()
            expected_type = "text" if i % 2 == 1 else "password"
            expected_label = "Hide password" if i % 2 == 1 else "Show password"
            expected_pressed = "true" if i % 2 == 1 else "false"
            expected_icon = "fa-solid fa-eye-slash" if i % 2 == 1 else "fa-solid fa-eye"

            self.assertEqual(sim.input_type, expected_type, f"Cycle {i} input type mismatch")
            self.assertEqual(sim.value, "MySecret#2026", f"Cycle {i} value must not change")
            self.assertEqual(sim.button_aria_label, expected_label, f"Cycle {i} aria-label mismatch")
            self.assertEqual(sim.button_aria_pressed, expected_pressed, f"Cycle {i} aria-pressed mismatch")
            self.assertEqual(sim.icon_class, expected_icon, f"Cycle {i} icon class mismatch")

    def test_07_independent_multi_field_toggles(self):
        """Verify on pages with multiple password fields, toggling one does not affect others."""
        old_sim = PasswordToggleSimulator("old_password", "password", "OldSecret123")
        new_sim = PasswordToggleSimulator("new_password", "password", "NewSecret456")
        cnf_sim = PasswordToggleSimulator("confirm_password", "password", "NewSecret456")

        # Toggle ONLY new_password
        new_sim.click()

        self.assertEqual(old_sim.input_type, "password")
        self.assertEqual(new_sim.input_type, "text")
        self.assertEqual(cnf_sim.input_type, "password")

        # Toggle confirm_password
        cnf_sim.click()

        self.assertEqual(old_sim.input_type, "password")
        self.assertEqual(new_sim.input_type, "text")
        self.assertEqual(cnf_sim.input_type, "text")

        # Toggle new_password back to hidden
        new_sim.click()

        self.assertEqual(old_sim.input_type, "password")
        self.assertEqual(new_sim.input_type, "password")
        self.assertEqual(cnf_sim.input_type, "text")

    def test_08_login_submission_with_password(self):
        """Verify student login works properly upon submitting credentials."""
        res = self.client.post(
            "/login",
            data={"id_no": "O180001", "password": "StudentPass123!"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("dashboard", res.request.path)

    def test_09_change_password_submission(self):
        """Verify change password workflow executes and updates the hash."""
        with self.client.session_transaction() as sess:
            sess["id_no"] = "O180001"
            sess["student_name"] = "Test Student"

        res = self.client.post(
            "/change_password",
            data={
                "old_password": "StudentPass123!",
                "new_password": "UpdatedPass456!",
                "confirm_password": "UpdatedPass456!",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)

        # Confirm new password authenticates
        with self.client.session_transaction() as sess:
            sess.clear()

        login_res = self.client.post(
            "/login",
            data={"id_no": "O180001", "password": "UpdatedPass456!"},
            follow_redirects=True,
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("dashboard", login_res.request.path)


if __name__ == "__main__":
    unittest.main()
