import unittest
import os
from app import app

class TestThemeSystem(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_html_path = os.path.join(self.base_dir, 'templates', 'base.html')
        self.style_css_path = os.path.join(self.base_dir, 'static', 'css', 'style.css')
        self.script_js_path = os.path.join(self.base_dir, 'static', 'js', 'script.js')
        self.charts_js_path = os.path.join(self.base_dir, 'static', 'js', 'charankumar', 'charts.js')

    def test_anti_fout_script_in_head(self):
        """Verify the synchronous anti-FOUT script is in <head> before stylesheets."""
        with open(self.base_html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for synchronous anti-FOUT script
        self.assertIn('<script>', content)
        self.assertIn('localStorage.getItem("theme")', content)
        self.assertIn('matchMedia("(prefers-color-scheme: dark)")', content)
        self.assertIn('document.documentElement.setAttribute("data-theme"', content)

        # Ensure script is placed before stylesheet link
        script_pos = content.find('localStorage.getItem("theme")')
        style_pos = content.find('css/style.css')
        self.assertTrue(script_pos < style_pos, "Anti-FOUT script must execute BEFORE stylesheets load")

    def test_theme_toggle_buttons_markup(self):
        """Verify desktop and mobile theme toggle buttons exist with full accessibility attributes."""
        with open(self.base_html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check mobile button
        self.assertIn('id="mobileThemeToggle"', content)
        self.assertIn('class="theme-toggle-btn"', content)
        self.assertIn('aria-label="Switch to dark mode"', content)
        self.assertIn('aria-pressed="false"', content)

        # Check desktop button
        self.assertIn('id="themeToggle"', content)
        self.assertIn('fa-moon', content)

    def test_css_variables_and_dark_tokens(self):
        """Verify :root and [data-theme="dark"] tokens exist in style.css."""
        with open(self.style_css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        # Root tokens
        self.assertIn(':root {', css)
        self.assertIn('--bg-body:', css)
        self.assertIn('--bg-surface:', css)
        self.assertIn('--primary: #ff6b4a;', css)

        # Dark tokens
        self.assertIn('[data-theme="dark"] {', css)
        self.assertIn('--bg-body: #0b0f19;', css)
        self.assertIn('--bg-surface: #111827;', css)
        self.assertIn('--border-color: #243044;', css)

        # Theme toggle button styling
        self.assertIn('.theme-toggle-btn {', css)
        self.assertIn('.theme-toggle-btn:hover {', css)

        # Comprehensive dark component overrides
        self.assertIn('[data-theme="dark"] .card', css)
        self.assertIn('[data-theme="dark"] .login-wrapper', css)
        self.assertIn('[data-theme="dark"] .admin-login-card', css)
        self.assertIn('[data-theme="dark"] .form-control', css)
        self.assertIn('[data-theme="dark"] .welcome-hero', css)
        self.assertIn('[data-theme="dark"] .table thead th', css)

    def test_js_theme_engine(self):
        """Verify Theme Management logic in static/js/script.js."""
        with open(self.script_js_path, 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn('function getPreferredTheme()', js)
        self.assertIn('function syncThemeUI(theme)', js)
        self.assertIn('function setTheme(newTheme)', js)
        self.assertIn('new CustomEvent("themeChanged"', js)
        self.assertIn('.theme-toggle-btn', js)
        self.assertIn('matchMedia("(prefers-color-scheme: dark)")', js)

    def test_charts_dynamic_theme_integration(self):
        """Verify dynamic theme adaptation in charts.js."""
        with open(self.charts_js_path, 'r', encoding='utf-8') as f:
            charts_js = f.read()

        self.assertIn('function getChartColors()', charts_js)
        self.assertIn('themeChanged', charts_js)
        self.assertIn('activeCharts', charts_js)
        self.assertIn('chart.update()', charts_js)

    def test_rendered_pages_have_toggle_markup(self):
        """Verify rendered HTML responses have the theme toggle components."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('mobileThemeToggle', html)
        self.assertIn('themeToggle', html)
        self.assertIn('theme-toggle-btn', html)
        self.assertIn('data-theme', html)

if __name__ == '__main__':
    unittest.main()
