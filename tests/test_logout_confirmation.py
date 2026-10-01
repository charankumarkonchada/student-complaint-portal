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
import backend.config as config
os.environ["TESTING"] = "1"
from app import create_app
from backend.database.db import get_db_connection
from backend.database.queries import init_database

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

            # 2. Navbar logout trigger points to admin logout inside account dropdown
            admin_logout_links = [l for l in parser.logout_links if l.get("href") == "/admin_logout"]
            self.assertTrue(len(admin_logout_links) >= 1, f"Admin logout link missing on {url}")

            # 3. Verify admin account dropdown exists and is properly structured
            self.assertIn('id="adminUserDropdown"', html, f"Admin account dropdown trigger missing on {url}")
            self.assertIn('data-bs-toggle="dropdown"', html, f"Admin dropdown toggle missing on {url}")
            self.assertIn('Administrator', html, f"Administrator label missing on {url}")
            self.assertIn('Hostel Incharge', html, f"Hostel Incharge role missing on {url}")

            # 4. On Admin Dashboard, verify standalone banner logout button is removed (unified in dropdown)
            if url == "/admin_dashboard":
                self.assertEqual(len(admin_logout_links), 1, "Admin Dashboard should have unified account dropdown logout button, not redundant banner logout")
                self.assertIn("System Active", html, "System Active indicator should remain intact")

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

    # -------------------------------------------------------------------------
    # 6. NO-CACHE & SECURITY HEADERS FOR AUTHENTICATED AND LOGOUT RESPONSES
    # -------------------------------------------------------------------------
    def test_10_authenticated_student_pages_send_no_cache_headers(self):
        """Verify authenticated student pages send no-store/no-cache headers."""
        self._login_student()
        for endpoint in ["/dashboard", "/profile", "/complaints", "/activity", "/notifications"]:
            res = self.client.get(endpoint)
            self.assertEqual(res.status_code, 200, f"Expected 200 for {endpoint}")
            self.assertIn("no-store", res.headers.get("Cache-Control", ""))
            self.assertIn("no-cache", res.headers.get("Cache-Control", ""))
            self.assertIn("must-revalidate", res.headers.get("Cache-Control", ""))
            self.assertEqual(res.headers.get("Pragma"), "no-cache")
            self.assertEqual(res.headers.get("Expires"), "0")

    def test_11_authenticated_admin_pages_send_no_cache_headers(self):
        """Verify authenticated admin pages send no-store/no-cache headers."""
        self._login_admin()
        for endpoint in ["/admin_dashboard", "/manage_complaints", "/analytics", "/admin/common_issues"]:
            res = self.client.get(endpoint)
            self.assertEqual(res.status_code, 200, f"Expected 200 for {endpoint}")
            self.assertIn("no-store", res.headers.get("Cache-Control", ""))
            self.assertIn("no-cache", res.headers.get("Cache-Control", ""))
            self.assertIn("must-revalidate", res.headers.get("Cache-Control", ""))
            self.assertEqual(res.headers.get("Pragma"), "no-cache")
            self.assertEqual(res.headers.get("Expires"), "0")

    def test_12_logout_responses_send_no_cache_headers(self):
        """Verify logout responses (redirects) send no-store/no-cache headers."""
        self._login_student()
        res_stud = self.client.post("/logout", data={"csrf_token": self._csrf()}, follow_redirects=False)
        self.assertEqual(res_stud.status_code, 302)
        self.assertIn("no-store", res_stud.headers.get("Cache-Control", ""))
        self.assertEqual(res_stud.headers.get("Pragma"), "no-cache")
        self.assertEqual(res_stud.headers.get("Expires"), "0")

        self._login_admin()
        res_adm = self.client.post("/admin_logout", data={"csrf_token": self._csrf()}, follow_redirects=False)
        self.assertEqual(res_adm.status_code, 302)
        self.assertIn("no-store", res_adm.headers.get("Cache-Control", ""))
        self.assertEqual(res_adm.headers.get("Pragma"), "no-cache")
        self.assertEqual(res_adm.headers.get("Expires"), "0")

    def test_13_public_pages_do_not_send_no_store_headers(self):
        """Verify public guest pages do not send restrictive authenticated no-store headers."""
        for endpoint in ["/", "/login", "/admin_login", "/register"]:
            res = self.client.get(endpoint)
            self.assertEqual(res.status_code, 200)
            self.assertNotIn("no-store", res.headers.get("Cache-Control", ""))

    def test_14_authenticated_page_data_attribute_and_bfcache_script(self):
        """Verify data-authenticated attribute is set on authenticated pages and absent on public pages."""
        self._login_student()
        res_dash = self.client.get("/dashboard")
        html_dash = res_dash.get_data(as_text=True)
        self.assertIn('data-authenticated="true"', html_dash)
        self.assertIn('data-auth-user="student"', html_dash)
        self.assertIn('window.addEventListener("pageshow"', html_dash)

        self.client.post("/logout", data={"csrf_token": self._csrf()}, follow_redirects=True)
        res_public = self.client.get("/")
        html_public = res_public.get_data(as_text=True)
        self.assertNotIn('data-authenticated="true"', html_public)

    def test_15_auth_status_api_endpoint(self):
        """Verify /api/auth/status endpoint for BFCache/multi-tab verification."""
        # Unauthenticated
        with self.client.session_transaction() as sess:
            sess.clear()
        res = self.client.get("/api/auth/status")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data.get("authenticated"))

        # Student authenticated
        self._login_student()
        res_s = self.client.get("/api/auth/status")
        self.assertEqual(res_s.status_code, 200)
        data_s = res_s.get_json()
        self.assertTrue(data_s.get("authenticated"))
        self.assertEqual(data_s.get("role"), "student")

        # Admin authenticated
        with self.client.session_transaction() as sess:
            sess.clear()
        self._login_admin()
        res_a = self.client.get("/api/auth/status")
        self.assertEqual(res_a.status_code, 200)
        data_a = res_a.get_json()
        self.assertTrue(data_a.get("authenticated"))
        self.assertEqual(data_a.get("role"), "admin")

    def test_16_logged_out_post_to_authenticated_route_redirects_to_login(self):
        """Verify that state-changing POST from stale page after logout redirects to login instead of 400 CSRF error."""
        with self.client.session_transaction() as sess:
            sess.clear()
        # Enable CSRF to test production behavior
        self.app.config["WTF_CSRF_ENABLED"] = True
        try:
            # Student logout -> POST to student route redirects to /login
            res_student_post = self.client.post("/profile/request_id_correction", data={
                "csrf_token": "stale-token",
                "requested_id": "O221169",
                "reason": "Stale post after logout"
            }, follow_redirects=False)
            self.assertEqual(res_student_post.status_code, 302)
            self.assertIn("/login", res_student_post.headers.get("Location", ""))

            # Admin logout -> POST to admin route redirects to /admin_login
            res_admin_post = self.client.post("/update_status/1", data={
                "csrf_token": "stale-token",
                "status": "In Progress"
            }, follow_redirects=False)
            self.assertEqual(res_admin_post.status_code, 302)
            self.assertIn("/admin_login", res_admin_post.headers.get("Location", ""))
        finally:
            self.app.config["WTF_CSRF_ENABLED"] = False

    def test_17_authenticated_post_with_invalid_csrf_still_aborts_400(self):
        """Verify that genuine CSRF attack while authenticated is still rejected with 400 Bad Request."""
        self._login_student()
        self.app.config["WTF_CSRF_ENABLED"] = True
        try:
            # Post with invalid CSRF token while authenticated
            res = self.client.post("/profile/request_id_correction", data={
                "csrf_token": "tampered-csrf-token",
                "requested_id": "O221169",
                "reason": "CSRF attack attempt"
            })
            self.assertEqual(res.status_code, 400)
            self.assertIn("Invalid or missing CSRF token", res.get_data(as_text=True))
        finally:
            self.app.config["WTF_CSRF_ENABLED"] = False

    def test_18_browser_back_simulation_after_logout(self):
        """Verify simulated browser Back navigation after logout redirects to login."""
        # 1. Admin login -> logout -> back to dashboard
        self._login_admin()
        res_logout = self.client.post("/admin_logout", data={"csrf_token": self._csrf()}, follow_redirects=True)
        self.assertEqual(res_logout.status_code, 200)

        # Back navigation requests dashboard
        res_back = self.client.get("/admin_dashboard", follow_redirects=False)
        self.assertEqual(res_back.status_code, 302)
        self.assertIn("/admin_login", res_back.headers.get("Location", ""))

        # 2. Student login -> logout -> back to dashboard
        self._login_student()
        res_s_logout = self.client.post("/logout", data={"csrf_token": self._csrf()}, follow_redirects=True)
        self.assertEqual(res_s_logout.status_code, 200)

        res_s_back = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(res_s_back.status_code, 302)
        self.assertIn("/login", res_s_back.headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main()
