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
os.environ["TESTING"] = "1"
from app import create_app
from database.db import get_db_connection
from database.queries import init_database

TEST_DB_PATH = os.path.join(BASE_DIR, "test_logout_confirm.db")


class LogoutModalParser(HTMLParser):
    """Parses HTML to inspect modal and logout button elements."""
    def __init__(self):
        super().__init__()
        self.has_logout_modal = False
        self.modal_attrs = {}
        self.has_cancel_btn = False
        self.cancel_btn_attrs = {}
        self.has_confirm_btn = False
        self.confirm_btn_attrs = {}
        self.has_close_btn = False
        self.logout_links = []
        self.text_content = []
        self._current_tag = None
        self._in_title = False
        self._in_desc = False
        self.modal_title = ""
        self.modal_desc = ""

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        tag_id = attr_dict.get("id", "")
        tag_classes = attr_dict.get("class", "").split()

        if tag_id == "logoutConfirmModal":
            self.has_logout_modal = True
            self.modal_attrs = attr_dict

        if tag_id == "logoutCancelBtn":
            self.has_cancel_btn = True
            self.cancel_btn_attrs = attr_dict

        if tag_id == "logoutConfirmBtn":
            self.has_confirm_btn = True
            self.confirm_btn_attrs = attr_dict

        if "logout-close-btn" in tag_classes or (tag == "button" and "btn-close" in tag_classes and attr_dict.get("data-bs-dismiss") == "modal"):
            self.has_close_btn = True

        if "nav-btn-logout" in tag_classes or attr_dict.get("data-logout-trigger") == "true":
            self.logout_links.append(attr_dict)

        if tag_id == "logoutModalTitle":
            self._in_title = True
        if tag_id == "logoutModalDesc":
            self._in_desc = True

    def handle_endtag(self, tag):
        self._in_title = False
        self._in_desc = False

    def handle_data(self, data):
        if self._in_title:
            self.modal_title += data.strip()
        if self._in_desc:
            self.modal_desc += data.strip()


class TestLogoutConfirmation(unittest.TestCase):
    def _csrf(self):
        with self.client.session_transaction() as sess:
            return sess.get("_csrf_token") or ""

    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

        config.DATABASE_URL = ""
        config.DATABASE = TEST_DB_PATH
        config.SECRET_KEY = "test-secret-key-logout"

        init_database()
        cls.app = create_app()
        cls.app.config.update({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
        })

        # Seed test student and admin
        conn = get_db_connection()
        cur = conn.cursor()
        pw_hash = generate_password_hash("Student@123")
        cur.execute(
            """
            INSERT OR REPLACE INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("Charan Kumar", "0221168", "charan@rguktong.ac.in", "9876543210", "BH-1", "108", pw_hash)
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def setUp(self):
        self.client = self.app.test_client()

    def _login_student(self):
        return self.client.post("/login", data={
            "id_no": "0221168",
            "password": "Student@123"
        }, follow_redirects=True)

    def _login_admin(self):
        return self.client.post("/admin_login", data={
            "username": config.ADMIN_USERNAME,
            "password": config.ADMIN_PASSWORD
        }, follow_redirects=True)

    # -------------------------------------------------------------------------
    # 1. GUEST PAGES: NO LOGOUT MODAL
    # -------------------------------------------------------------------------
    def test_01_guest_pages_do_not_render_logout_modal(self):
        guest_urls = ["/", "/login", "/register", "/admin_login"]
        for url in guest_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200)
            parser = LogoutModalParser()
            parser.feed(res.get_data(as_text=True))
            self.assertFalse(parser.has_logout_modal, f"Modal should not exist on guest page {url}")
            self.assertEqual(len(parser.logout_links), 0, f"No logout links on guest page {url}")

    # -------------------------------------------------------------------------
    # 2. STUDENT PAGES: LOGOUT MODAL & ELEMENTS
    # -------------------------------------------------------------------------
    def test_02_student_pages_render_logout_modal_and_trigger(self):
        self._login_student()
        student_urls = ["/dashboard", "/complaints", "/notifications", "/activity", "/profile"]
        for url in student_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Failed loading {url}")
            html = res.get_data(as_text=True)

            parser = LogoutModalParser()
            parser.feed(html)

            # 1. Modal container exists
            self.assertTrue(parser.has_logout_modal, f"Logout modal missing on {url}")

            # 2. WCAG Accessibility attributes
            self.assertEqual(parser.modal_attrs.get("role"), "dialog")
            self.assertEqual(parser.modal_attrs.get("aria-modal"), "true")
            self.assertEqual(parser.modal_attrs.get("aria-labelledby"), "logoutModalTitle")
            self.assertEqual(parser.modal_attrs.get("aria-describedby"), "logoutModalDesc")
            self.assertEqual(parser.modal_attrs.get("tabindex"), "-1")

            # 3. Content
            self.assertIn("Confirm Logout", parser.modal_title)
            self.assertIn("Are you sure you want to logout from IntelliHostel?", parser.modal_desc)

            # 4. Buttons
            self.assertTrue(parser.has_cancel_btn, f"Cancel button missing on {url}")
            self.assertEqual(parser.cancel_btn_attrs.get("data-bs-dismiss"), "modal")
            self.assertTrue(parser.has_confirm_btn, f"Confirm button missing on {url}")

            # 5. Navbar logout trigger points to student logout
            student_logout_links = [l for l in parser.logout_links if l.get("href") == "/logout"]
            self.assertTrue(len(student_logout_links) >= 1, f"Student logout link missing on {url}")

    # -------------------------------------------------------------------------
    # 3. ADMIN PAGES: LOGOUT MODAL & DUAL TRIGGERS
    # -------------------------------------------------------------------------
    def test_03_admin_pages_render_logout_modal_and_trigger(self):
        self._login_admin()
        admin_urls = ["/admin_dashboard", "/manage_complaints", "/admin/common_issues", "/analytics"]
        for url in admin_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Failed loading {url}")
            html = res.get_data(as_text=True)

            parser = LogoutModalParser()
            parser.feed(html)

            # 1. Modal container exists
            self.assertTrue(parser.has_logout_modal, f"Logout modal missing on {url}")
            self.assertTrue(parser.has_cancel_btn)
            self.assertTrue(parser.has_confirm_btn)

            # 2. Navbar logout trigger points to admin logout
            admin_logout_links = [l for l in parser.logout_links if l.get("href") == "/admin_logout"]
            self.assertTrue(len(admin_logout_links) >= 1, f"Admin logout link missing on {url}")

            # 3. On Admin Dashboard, check that both banner button and navbar have admin_logout
            if url == "/admin_dashboard":
                self.assertTrue(len(admin_logout_links) >= 2, "Admin Dashboard should have both navbar and banner logout buttons")

    # -------------------------------------------------------------------------
    # 4. CANCEL FLOW: SESSION REMAINS COMPLETELY INTACT
    # -------------------------------------------------------------------------
    def test_04_student_cancel_logout_keeps_session_active(self):
        self._login_student()

        # Check authenticated dashboard
        dash = self.client.get("/dashboard")
        self.assertEqual(dash.status_code, 200)
        self.assertIn("Charan Kumar", dash.get_data(as_text=True))

        # Simulating user clicking Cancel (modal dismisses client-side without hitting /logout)
        # Verify subsequent requests remain authenticated
        profile = self.client.get("/profile")
        self.assertEqual(profile.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("student_id"), 1)
            self.assertEqual(sess.get("id_no"), "0221168")

    def test_05_admin_cancel_logout_keeps_session_active(self):
        self._login_admin()

        # Check admin dashboard
        dash = self.client.get("/admin_dashboard")
        self.assertEqual(dash.status_code, 200)

        # Simulating cancel: session is not cleared
        mgmt = self.client.get("/manage_complaints")
        self.assertEqual(mgmt.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("admin"), config.ADMIN_USERNAME)

    # -------------------------------------------------------------------------
    # 5. BACKEND LOGOUT EXECUTION: SESSIONS CLEARED & REDIRECTED
    # -------------------------------------------------------------------------
    def test_06_student_logout_clears_session_and_redirects(self):
        self._login_student()
        with self.client.session_transaction() as sess:
            self.assertIsNotNone(sess.get("student_id"))

        # Trigger backend logout route
        res = self.client.post("/logout", data={"csrf_token": self._csrf()}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Logged Out Successfully", res.get_data(as_text=True))

        # Verify session is empty
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("student_id"))
            self.assertIsNone(sess.get("id_no"))

        # Protected page redirects to student login
        protected = self.client.get("/dashboard", follow_redirects=True)
        self.assertIn("Student Login", protected.get_data(as_text=True))

    def test_07_admin_logout_clears_session_and_redirects(self):
        self._login_admin()
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("admin"), config.ADMIN_USERNAME)

        # Trigger backend admin logout route
        res = self.client.post("/admin_logout", data={"csrf_token": self._csrf()}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Admin Logged Out Successfully", res.get_data(as_text=True))

        # Verify session is empty
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("admin"))

        # Protected admin page redirects to admin login
        protected = self.client.get("/admin_dashboard", follow_redirects=True)
        self.assertIn("Admin Portal", protected.get_data(as_text=True))

    def test_08_student_cannot_access_profile_or_dashboard_after_logout(self):
        """Verify student cannot access /profile or /dashboard after logout."""
        self._login_student()
        # Verify /profile is accessible before logout
        res_before = self.client.get("/profile")
        self.assertEqual(res_before.status_code, 200)
        self.assertIn("Student Profile", res_before.get_data(as_text=True))

        # Logout
        res_logout = self.client.post("/logout", data={"csrf_token": self._csrf()}, follow_redirects=True)
        self.assertEqual(res_logout.status_code, 200)

        # Access /profile -> must redirect to login
        res_prof = self.client.get("/profile", follow_redirects=True)
        self.assertEqual(res_prof.status_code, 200)
        self.assertIn("Student Login", res_prof.get_data(as_text=True))
        self.assertNotIn("Personal & Hostel Details", res_prof.get_data(as_text=True))

        # Access /dashboard -> must redirect to login
        res_dash = self.client.get("/dashboard", follow_redirects=True)
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn("Student Login", res_dash.get_data(as_text=True))

    def test_09_logout_modal_form_has_csrf_and_valid_action(self):
        """Verify the rendered logout modal includes CSRF token and valid POST action."""
        self._login_student()
        res = self.client.get("/profile")
        html = res.get_data(as_text=True)
        self.assertIn('id="logoutConfirmModal"', html)
        self.assertIn('id="logoutConfirmForm"', html)
        self.assertIn('name="csrf_token"', html)
        self.assertIn('action="/logout"', html)


if __name__ == "__main__":
    unittest.main()
