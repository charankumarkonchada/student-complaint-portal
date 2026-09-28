import os
import sys
import pytest

# Ensure repository root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Set global testing environment variable
os.environ["TESTING"] = "1"
os.environ["FLASK_ENV"] = "testing"

import config
import smtplib


@pytest.fixture(autouse=True)
def isolate_email_in_tests(monkeypatch):
    """
    Centralized test safety fixture.
    1. Ensures TESTING is active in os.environ.
    2. Suppresses EMAIL_NOTIFICATIONS_ENABLED by default across all tests.
       (Email tests can explicitly patch config.EMAIL_NOTIFICATIONS_ENABLED to True).
    3. Blocks unmocked real SMTP network connections as an extra defense layer.
    """
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setattr(config, "EMAIL_NOTIFICATIONS_ENABLED", False, raising=False)

    # Safety interceptor: block any unmocked smtplib network connections
    def blocked_connect(self, host='localhost', port=0, source_address=None):
        raise RuntimeError(
            f"Blocked real SMTP connection attempt to {host}:{port} during automated test execution."
        )

    monkeypatch.setattr(smtplib.SMTP, "connect", blocked_connect)
    yield
