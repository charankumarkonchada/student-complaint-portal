import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import requests

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import backend.config as config

TEST_STORAGE_DB = os.path.join(BASE_DIR, "test_storage.db")
config.DATABASE_URL = ""
config.DATABASE = TEST_STORAGE_DB
config.SECRET_KEY = "test-storage-deletion-secret"
config.SUPABASE_URL = "https://mock-project.supabase.co"
config.SUPABASE_SERVICE_ROLE_KEY = "mock-service-role-key"
config.SUPABASE_STORAGE_BUCKET = "complaint-attachments"

os.environ["TESTING"] = "1"
from app import create_app
from backend.database.db import get_db_connection
from backend.database.queries import init_database
from backend.services.storage_service import (
    extract_storage_path,
    delete_from_cloud_storage
)


class TestStorageDeletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.DATABASE_URL = ""
        config.DATABASE = TEST_STORAGE_DB
        config.SUPABASE_URL = "https://mock-project.supabase.co"
        config.SUPABASE_SERVICE_ROLE_KEY = "mock-service-role-key"
        config.SUPABASE_STORAGE_BUCKET = "complaint-attachments"
        if os.path.exists(TEST_STORAGE_DB):
            try:
                os.remove(TEST_STORAGE_DB)
            except Exception:
                pass
        init_database()
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_STORAGE_DB):
            try:
                os.remove(TEST_STORAGE_DB)
            except Exception:
                pass

    def setUp(self):
        conn = get_db_connection()
        conn.execute("DELETE FROM complaint_history")
        conn.execute("DELETE FROM complaints")
        conn.execute("DELETE FROM students")

        # Seed student
        conn.execute(
            """
            INSERT INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (1, 'Storage Test Student', 'O210001', 'o210001@rguktong.ac.in', '9876543210', 'Hostel Block A', '101', 'pw')
            """
        )
        conn.commit()
        conn.close()

    def test_01_extract_storage_path_formats(self):
        """Verify storage path extraction handles full URLs, signed URLs, relative paths, and rejects invalid paths."""
        bucket = "complaint-attachments"

        # 1. Full public URL
        url = "https://mock-project.supabase.co/storage/v1/object/public/complaint-attachments/complaints/1/abc12345.jpg"
        self.assertEqual(extract_storage_path(url, bucket), "complaints/1/abc12345.jpg")

        # 2. Signed URL with query tokens
        signed_url = "https://mock-project.supabase.co/storage/v1/object/sign/complaint-attachments/complaints/1/abc12345.jpg?token=secret123"
        self.assertEqual(extract_storage_path(signed_url, bucket), "complaints/1/abc12345.jpg")

        # 3. Relative complaints path
        rel_path = "complaints/1/abc12345.jpg"
        self.assertEqual(extract_storage_path(rel_path, bucket), "complaints/1/abc12345.jpg")

        # 4. Local uploads path returns None
        self.assertIsNone(extract_storage_path("/static/uploads/abc.jpg", bucket))

        # 5. Empty or None returns None
        self.assertIsNone(extract_storage_path("", bucket))
        self.assertIsNone(extract_storage_path(None, bucket))
        self.assertIsNone(extract_storage_path("   ", bucket))

        # 6. Unrelated URL from another service or bucket
        self.assertIsNone(extract_storage_path("https://other-bucket.com/avatar.png", bucket))

    def test_02_single_complaint_image_deleted_correctly(self):
        """Verify one complaint image is deleted correctly via Supabase Storage API."""
        image_url = "https://mock-project.supabase.co/storage/v1/object/public/complaint-attachments/complaints/1/fan_broken_01.png"

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"name": "complaints/1/fan_broken_01.png"}]

        with patch("requests.delete", return_value=mock_resp) as mock_delete:
            success = delete_from_cloud_storage(image_url)
            self.assertTrue(success)

            mock_delete.assert_called_once()
            called_url = mock_delete.call_args[0][0]
            called_kwargs = mock_delete.call_args[1]

            # Verify target URL is storage API endpoint for the bucket
            expected_endpoint = "https://mock-project.supabase.co/storage/v1/object/complaint-attachments"
            self.assertEqual(called_url, expected_endpoint)

            # Verify prefixes contains only the exact complaint image path
            self.assertEqual(called_kwargs["json"], {"prefixes": ["complaints/1/fan_broken_01.png"]})

            # Verify authentication headers
            self.assertEqual(called_kwargs["headers"]["Authorization"], "Bearer mock-service-role-key")
            self.assertEqual(called_kwargs["headers"]["apikey"], "mock-service-role-key")
            self.assertEqual(called_kwargs["headers"]["Content-Type"], "application/json")

    def test_03_multiple_images_deleted_correctly(self):
        """Verify multiple complaint images are deleted in a single batched call."""
        images = [
            "https://mock-project.supabase.co/storage/v1/object/public/complaint-attachments/complaints/1/img_01.png",
            "complaints/1/img_02.jpg",
            "https://mock-project.supabase.co/storage/v1/object/sign/complaint-attachments/complaints/1/img_03.png?token=xyz"
        ]

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200

        with patch("requests.delete", return_value=mock_resp) as mock_delete:
            success = delete_from_cloud_storage(images)
            self.assertTrue(success)

            mock_delete.assert_called_once()
            called_prefixes = mock_delete.call_args[1]["json"]["prefixes"]
            self.assertEqual(
                called_prefixes,
                ["complaints/1/img_01.png", "complaints/1/img_02.jpg", "complaints/1/img_03.png"]
            )

    def test_04_unrelated_images_not_deleted(self):
        """Verify that unrelated images and invalid paths are never included in deletion request."""
        # Mix of valid complaint image, local upload, empty string, and external/unrelated image
        mixed_refs = [
            "https://mock-project.supabase.co/storage/v1/object/public/complaint-attachments/complaints/1/valid_complaint_image.png",
            "/static/uploads/local_file.jpg",
            "",
            "   ",
            "https://external-domain.com/unrelated_user_photo.jpg"
        ]

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200

        with patch("requests.delete", return_value=mock_resp) as mock_delete:
            success = delete_from_cloud_storage(mixed_refs)
            self.assertTrue(success)

            mock_delete.assert_called_once()
            called_prefixes = mock_delete.call_args[1]["json"]["prefixes"]
            # Must ONLY contain the one valid complaint attachment
            self.assertEqual(called_prefixes, ["complaints/1/valid_complaint_image.png"])
            self.assertNotIn("local_file.jpg", str(called_prefixes))
            self.assertNotIn("unrelated_user_photo.jpg", str(called_prefixes))

    def test_05_missing_attachment_paths_handled_safely(self):
        """Verify that missing, empty, or None attachment paths are safely handled without API calls."""
        with patch("requests.delete") as mock_delete:
            # None
            self.assertTrue(delete_from_cloud_storage(None))
            # Empty string
            self.assertTrue(delete_from_cloud_storage(""))
            # Whitespace
            self.assertTrue(delete_from_cloud_storage("   "))
            # Empty list
            self.assertTrue(delete_from_cloud_storage([]))
            # List of invalid/empty
            self.assertTrue(delete_from_cloud_storage(["", None, "/static/uploads/nonexistent.jpg"]))

            # requests.delete should NEVER have been invoked
            mock_delete.assert_not_called()

    def test_06_storage_deletion_failure_handled_safely(self):
        """Verify that HTTP error or network exception from Supabase Storage is logged and returns False."""
        # 1. HTTP 500 error from Supabase
        mock_error_resp = MagicMock()
        mock_error_resp.ok = False
        mock_error_resp.status_code = 500
        mock_error_resp.text = "Internal Server Error"

        with patch("requests.delete", return_value=mock_error_resp):
            success = delete_from_cloud_storage("complaints/1/photo.jpg")
            self.assertFalse(success)

        # 2. Network exception / timeout
        with patch("requests.delete", side_effect=requests.RequestException("Connection timed out")):
            success = delete_from_cloud_storage("complaints/1/photo.jpg")
            self.assertFalse(success)

    def test_07_route_delete_complaint_triggers_storage_cleanup(self):
        """Integration test: Deleting a complaint via POST /complaint/<id>/delete triggers storage cleanup."""
        # Create complaint with attachment in DB
        conn = get_db_connection()
        cur = conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status, image)
            VALUES (1, 'Electrical', 'Ceiling spark', 'Sparks seen', 'High', 'Pending', ?)
            """,
            ("https://mock-project.supabase.co/storage/v1/object/public/complaint-attachments/complaints/1/spark_photo.png",)
        )
        complaint_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Log in as Student 1
        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["role"] = "student"
            sess["name"] = "Storage Test Student"

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200

        with patch("requests.delete", return_value=mock_resp) as mock_delete:
            res = self.client.post(f"/complaint/{complaint_id}/delete", follow_redirects=True)
            self.assertEqual(res.status_code, 200)

            # Database record must be deleted
            conn = get_db_connection()
            deleted_record = conn.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,)).fetchone()
            conn.close()
            self.assertIsNone(deleted_record)

            # Storage API must have been called to delete the exact image
            mock_delete.assert_called_once()
            called_prefixes = mock_delete.call_args[1]["json"]["prefixes"]
            self.assertEqual(called_prefixes, ["complaints/1/spark_photo.png"])

    def test_08_route_delete_complaint_without_attachment_succeeds(self):
        """Integration test: Deleting a complaint without attachment deletes from DB without Storage calls."""
        conn = get_db_connection()
        cur = conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status, image)
            VALUES (1, 'Carpentry', 'Door squeak', 'Squeaking hinges', 'Low', 'Pending', NULL)
            """,
        )
        complaint_id = cur.lastrowid
        conn.commit()
        conn.close()

        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["role"] = "student"
            sess["name"] = "Storage Test Student"

        with patch("requests.delete") as mock_delete:
            res = self.client.post(f"/delete_complaint/{complaint_id}", follow_redirects=True)
            self.assertEqual(res.status_code, 200)

            # Database record must be deleted
            conn = get_db_connection()
            deleted_record = conn.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,)).fetchone()
            conn.close()
            self.assertIsNone(deleted_record)

            # Storage API must NOT have been called
            mock_delete.assert_not_called()

    def test_09_route_delete_complaint_resilient_to_storage_failure(self):
        """Integration test: Database complaint deletion succeeds even if Supabase Storage deletion fails."""
        conn = get_db_connection()
        cur = conn.execute(
            """
            INSERT INTO complaints (student_id, category, title, description, priority, status, image)
            VALUES (1, 'Cleaning', 'Dusty room', 'Dust on desk', 'Low', 'Pending', ?)
            """,
            ("complaints/1/dust_photo.png",)
        )
        complaint_id = cur.lastrowid
        conn.commit()
        conn.close()

        with self.client.session_transaction() as sess:
            sess["student_id"] = 1
            sess["role"] = "student"
            sess["name"] = "Storage Test Student"

        mock_error_resp = MagicMock()
        mock_error_resp.ok = False
        mock_error_resp.status_code = 502
        mock_error_resp.text = "Bad Gateway"

        with patch("requests.delete", return_value=mock_error_resp):
            res = self.client.post(f"/complaint/{complaint_id}/delete", follow_redirects=True)
            self.assertEqual(res.status_code, 200)

            # Database record must still be deleted
            conn = get_db_connection()
            deleted_record = conn.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,)).fetchone()
            conn.close()
            self.assertIsNone(deleted_record)
            self.assertIn(b"Complaint Deleted Successfully", res.data)


if __name__ == "__main__":
    unittest.main()
