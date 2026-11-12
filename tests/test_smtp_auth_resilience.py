"""
Unit test suite verifying SMTP authentication resilience, RFC 3207 compliance,
port-to-protocol mapping, App Password sanitization, error handling, and safe logging.
"""
import unittest
from unittest.mock import patch, MagicMock, call
import logging
import smtplib
import ssl

import backend.config as config
from backend.services.email_service import (
    sanitize_smtp_password,
    resolve_smtp_mode,
    send_otp_email,
    send_email,
    _connect_and_send,
    _dispatch_smtp_message
)
from email.message import EmailMessage


class TestSMTPAuthResilience(unittest.TestCase):
    def setUp(self):
        self.original_host = getattr(config, "SMTP_HOST", "smtp.gmail.com")
        self.original_port = getattr(config, "SMTP_PORT", 587)
        self.original_user = getattr(config, "SMTP_USERNAME", "")
        self.original_pass = getattr(config, "SMTP_PASSWORD", "")
        self.original_from = getattr(config, "MAIL_FROM", "")
        self.original_tls = getattr(config, "SMTP_USE_TLS", True)
        self.original_enabled = getattr(config, "EMAIL_NOTIFICATIONS_ENABLED", True)

    def tearDown(self):
        config.SMTP_HOST = self.original_host
        config.SMTP_PORT = self.original_port
        config.SMTP_USERNAME = self.original_user
        config.SMTP_PASSWORD = self.original_pass
        config.MAIL_FROM = self.original_from
        config.SMTP_USE_TLS = self.original_tls
        config.EMAIL_NOTIFICATIONS_ENABLED = self.original_enabled

    # -------------------------------------------------------------------------
    # 1. Mode Resolution & Port Pairing
    # -------------------------------------------------------------------------
    def test_mode_resolution_port_465_always_uses_ssl(self):
        """Port 465 must always map to implicit SSL, even if SMTP_USE_TLS is True."""
        self.assertEqual(resolve_smtp_mode(465, use_tls=True), "SSL")
        self.assertEqual(resolve_smtp_mode(465, use_tls=False), "SSL")

    def test_mode_resolution_port_587_and_2525_use_starttls(self):
        """Port 587 and 2525 must always map to STARTTLS."""
        self.assertEqual(resolve_smtp_mode(587, use_tls=True), "STARTTLS")
        self.assertEqual(resolve_smtp_mode(587, use_tls=False), "STARTTLS")
        self.assertEqual(resolve_smtp_mode(2525, use_tls=True), "STARTTLS")

    def test_mode_resolution_custom_ports_respect_flag(self):
        """Custom ports should respect the explicit use_tls boolean flag."""
        self.assertEqual(resolve_smtp_mode(25, use_tls=False), "SSL")
        self.assertEqual(resolve_smtp_mode(25, use_tls=True), "STARTTLS")

    # -------------------------------------------------------------------------
    # 2. App Password Sanitization
    # -------------------------------------------------------------------------
    def test_sanitize_smtp_password_strips_gmail_app_password_spaces(self):
        """Gmail 16-character App Passwords generated with spaces must be sanitized."""
        raw_app_pw = "abcd efgh ijkl mnop"
        sanitized = sanitize_smtp_password(raw_app_pw, host="smtp.gmail.com")
        self.assertEqual(sanitized, "abcdefghijklmnop")

    def test_sanitize_smtp_password_strips_whitespace(self):
        """Standard passwords with leading or trailing whitespace must be trimmed."""
        raw_pw = "  secret_password_123  \n"
        sanitized = sanitize_smtp_password(raw_pw, host="smtp.sendgrid.net")
        self.assertEqual(sanitized, "secret_password_123")

    # -------------------------------------------------------------------------
    # 3. STARTTLS Connection Sequencing & RFC 3207
    # -------------------------------------------------------------------------
    @patch("smtplib.SMTP")
    def test_starttls_sequencing_on_port_587(self, mock_smtp_cls):
        """
        Verify that port 587 uses smtplib.SMTP, invokes EHLO before and after STARTTLS,
        passes an SSL context, and logs in before sending.
        """
        mock_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_instance

        msg = EmailMessage()
        msg["Subject"] = "Test STARTTLS"
        msg["From"] = "sender@example.com"
        msg["To"] = "student@rguktong.ac.in"
        msg.set_content("Hello")

        _connect_and_send(
            host="smtp.gmail.com",
            port=587,
            mode="STARTTLS",
            username="sender@example.com",
            password="cleanpassword123",
            msg=msg,
            timeout=15
        )

        mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=15)
        # Verify EHLO was called twice (pre and post-STARTTLS for RFC 3207 compliance)
        self.assertGreaterEqual(mock_instance.ehlo.call_count, 2)
        mock_instance.starttls.assert_called_once()
        mock_instance.login.assert_called_once_with("sender@example.com", "cleanpassword123")
        mock_instance.send_message.assert_called_once_with(msg)

    # -------------------------------------------------------------------------
    # 4. Implicit SSL Connection Sequencing
    # -------------------------------------------------------------------------
    @patch("smtplib.SMTP_SSL")
    @patch("smtplib.SMTP")
    def test_implicit_ssl_sequencing_on_port_465(self, mock_smtp, mock_smtp_ssl):
        """
        Verify that port 465 uses smtplib.SMTP_SSL directly, never calls starttls,
        and logs in before sending.
        """
        mock_instance = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_instance

        msg = EmailMessage()
        msg["Subject"] = "Test SSL"
        msg["From"] = "sender@example.com"
        msg["To"] = "student@rguktong.ac.in"
        msg.set_content("Hello SSL")

        _connect_and_send(
            host="smtp.gmail.com",
            port=465,
            mode="SSL",
            username="sender@example.com",
            password="cleanpassword123",
            msg=msg,
            timeout=15
        )

        mock_smtp.assert_not_called()
        self.assertEqual(mock_smtp_ssl.call_count, 1)
        mock_instance.starttls.assert_not_called()
        mock_instance.login.assert_called_once_with("sender@example.com", "cleanpassword123")
        mock_instance.send_message.assert_called_once_with(msg)

    # -------------------------------------------------------------------------
    # 5. Safe Diagnostic Logging (Never Exposing Secrets)
    # -------------------------------------------------------------------------
    @patch("smtplib.SMTP")
    def test_diagnostic_logging_does_not_expose_credentials_or_otp(self, mock_smtp_cls):
        """Verify logger outputs connection details but never credentials or secret OTP."""
        mock_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_instance

        secret_otp = "987654"
        secret_password = "super-secret-password-xyz"

        with self.assertLogs("backend.services.email_service", level="INFO") as log_capture:
            with patch.object(config, "SMTP_USERNAME", "mailer@example.com"), \
                 patch.object(config, "SMTP_PASSWORD", secret_password), \
                 patch.object(config, "MAIL_FROM", "mailer@example.com"), \
                 patch.object(config, "SMTP_PORT", 587), \
                 patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", True):
                send_otp_email("student@rguktong.ac.in", secret_otp)

        full_logs = "\n".join(log_capture.output)
        # Safe diagnostics present
        self.assertIn("Initiating SMTP connection to smtp.gmail.com:587", full_logs)
        self.assertIn("STARTTLS handshake successful", full_logs)
        self.assertIn("SMTP authentication successful", full_logs)

        # Sensitive secrets absent
        self.assertNotIn(secret_password, full_logs)
        self.assertNotIn(secret_otp, full_logs)

    # -------------------------------------------------------------------------
    # 6. Exception Handling in send_otp_email
    # -------------------------------------------------------------------------
    @patch("smtplib.SMTP")
    def test_send_otp_email_handles_smtp_server_disconnected_safely(self, mock_smtp_cls):
        """Verify SMTPServerDisconnected is caught, logged safely, and raises RuntimeError."""
        mock_instance = MagicMock()
        mock_instance.login.side_effect = smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
        mock_smtp_cls.return_value.__enter__.return_value = mock_instance

        with patch.object(config, "SMTP_USERNAME", "mailer@example.com"), \
             patch.object(config, "SMTP_PASSWORD", "secret123"), \
             patch.object(config, "MAIL_FROM", "mailer@example.com"), \
             patch.object(config, "SMTP_PORT", 587), \
             patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", True):
            with self.assertRaises(RuntimeError) as ctx:
                send_otp_email("student@rguktong.ac.in", "123456")

            self.assertIn("Unable to deliver OTP email", str(ctx.exception))
            self.assertIn("SMTPServerDisconnected", str(ctx.exception))

    @patch("smtplib.SMTP")
    def test_send_otp_email_handles_smtp_authentication_error_safely(self, mock_smtp_cls):
        """Verify SMTPAuthenticationError is caught, logged safely, and raises RuntimeError."""
        mock_instance = MagicMock()
        mock_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        mock_smtp_cls.return_value.__enter__.return_value = mock_instance

        with patch.object(config, "SMTP_USERNAME", "mailer@example.com"), \
             patch.object(config, "SMTP_PASSWORD", "secret123"), \
             patch.object(config, "MAIL_FROM", "mailer@example.com"), \
             patch.object(config, "SMTP_PORT", 587), \
             patch.object(config, "EMAIL_NOTIFICATIONS_ENABLED", True):
            with self.assertRaises(RuntimeError) as ctx:
                send_otp_email("student@rguktong.ac.in", "123456")

            self.assertIn("Unable to deliver OTP email", str(ctx.exception))
            self.assertIn("SMTPAuthenticationError", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 7. Auto-Fallback between Ports for Cloud/Serverless Environments
    # -------------------------------------------------------------------------
    @patch("backend.services.email_service.is_smtp_mocked", return_value=False)
    @patch("backend.services.email_service._connect_and_send")
    def test_dispatch_fallback_from_port_587_to_port_465(self, mock_connect, mock_is_mocked):
        """
        When port 587 disconnects unexpectedly in production (not mocked),
        the dispatcher automatically falls back to port 465 SSL.
        """
        mock_connect.side_effect = [
            smtplib.SMTPServerDisconnected("Connection unexpectedly closed"),
            None
        ]

        msg = EmailMessage()
        msg["Subject"] = "Test Fallback"
        msg["From"] = "mailer@example.com"
        msg["To"] = "student@rguktong.ac.in"
        msg.set_content("Fallback body")

        with patch.object(config, "SMTP_USERNAME", "mailer@example.com"), \
             patch.object(config, "SMTP_PASSWORD", "secret123"), \
             patch.object(config, "MAIL_FROM", "mailer@example.com"), \
             patch.object(config, "SMTP_HOST", "smtp.gmail.com"), \
             patch.object(config, "SMTP_PORT", 587):
            success = _dispatch_smtp_message(msg, "student@rguktong.ac.in", "Test Fallback", is_otp=False)

        self.assertTrue(success)
        self.assertEqual(mock_connect.call_count, 2)
        # Attempt 1: port 587, STARTTLS
        self.assertEqual(mock_connect.call_args_list[0].kwargs["port"], 587)
        self.assertEqual(mock_connect.call_args_list[0].kwargs["mode"], "STARTTLS")
        # Attempt 2: fallback to port 465, SSL
        self.assertEqual(mock_connect.call_args_list[1].kwargs["port"], 465)
        self.assertEqual(mock_connect.call_args_list[1].kwargs["mode"], "SSL")


if __name__ == "__main__":
    unittest.main()
