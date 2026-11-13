import os
import unittest
from app import app

class TestRegistrationUILayout(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.register_html_path = os.path.join(self.base_dir, 'frontend', 'templates', 'student', 'register.html')
        self.register_css_path = os.path.join(self.base_dir, 'frontend', 'static', 'css', 'rushmitha', 'register.css')
        self.logo_path = os.path.join(self.base_dir, 'frontend', 'static', 'images', 'student_complaint_portal_logo.jpeg')

    def test_01_logo_asset_exists(self):
        """Ensure the logo asset exists on the filesystem and is not removed."""
        self.assertTrue(os.path.isfile(self.logo_path), "student_complaint_portal_logo.jpeg must exist")
        self.assertGreater(os.path.getsize(self.logo_path), 0, "Logo image file must not be empty")

    def test_02_registration_page_markup(self):
        """Verify the registration page renders 200 OK and contains two-column layout elements."""
        res = self.client.get("/register")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Check two-column wrapper
        self.assertIn("register-wrapper", html)
        self.assertIn("register-brand", html)
        self.assertIn("register-form-panel", html)

        # Check logo image references
        self.assertIn("student_complaint_portal_logo.jpeg", html)
        self.assertIn("register-brand-logo", html)
        self.assertIn("register-header-logo", html)

        # Check headings and subtitles
        self.assertIn("IntelliHostel", html)
        self.assertIn("Student Registration", html)
        self.assertIn("Create your RGUKT student account", html)

        # Check all required form fields and IDs
        for field_id in ["name", "id_no", "email", "phone", "hostel", "room", "password", "confirm_password"]:
            self.assertIn(f'id="{field_id}"', html, f"Field {field_id} must be present in register form")

        # Check validation error elements
        for err_id in ["idError", "emailDomainError", "emailMismatchError", "passwordError"]:
            self.assertIn(f'id="{err_id}"', html, f"Validation container {err_id} must be present")

        # Check submit button and password toggles
        self.assertIn('id="regSubmitBtn"', html)
        self.assertIn('id="passwordToggle"', html)
        self.assertIn('id="confirmPasswordToggle"', html)

    def test_03_css_constrained_image_and_layout(self):
        """Verify register.css applies bounded dimensions, object-fit: contain, and responsive layout."""
        with open(self.register_css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Check object-fit: contain
        self.assertIn("object-fit: contain", css, "register.css must use object-fit: contain for logos")

        # Check bounded dimensions for .register-brand-logo
        self.assertIn(".register-brand-logo {", css)
        self.assertIn("max-width: 84px;", css)
        self.assertIn("max-height: 84px;", css)

        # Check bounded dimensions for .register-header-logo
        self.assertIn(".register-header-logo {", css)
        self.assertIn("max-width: 48px;", css)
        self.assertIn("max-height: 48px;", css)

        # Check two-column layout
        self.assertIn("grid-template-columns:", css)
        self.assertIn(".register-brand {", css)
        self.assertIn(".register-form-panel {", css)

        # Check responsive breakpoints
        self.assertIn("@media (max-width: 960px)", css)
        self.assertIn("@media (max-width: 480px)", css)

        # Check dark theme support
        self.assertIn('[data-theme="dark"]', css)

if __name__ == "__main__":
    unittest.main()
