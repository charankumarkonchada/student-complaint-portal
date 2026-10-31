import os
import sys
import io
import unittest
from unittest.mock import patch, MagicMock

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

venv_site = os.path.join(BASE_DIR, ".venv", "lib", "python3.13", "site-packages")
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.append(venv_site)

import backend.config as config

TEST_RES_DB = os.path.join(BASE_DIR, "test_resolution.db")
config.DATABASE_URL = ""
config.DATABASE = TEST_RES_DB
config.SECRET_KEY = "test-resolution-proof-secret"
config.ALLOW_SQLITE_FALLBACK = True
config.ALLOW_LOCAL_STORAGE_FALLBACK = True

os.environ["TESTING"] = "1"
from app import create_app
from backend.database.db import get_db_connection
from backend.database.queries import init_database
from backend.database.create_db import migrate_sqlite
from backend.services.storage_service import (
    upload_resolution_proof,
    extract_storage_path,
    delete_from_cloud_storage,
    allowed_file,
    _validate_content
)


def create_mock_image(format_type="jpg", size_bytes=1024):
    """Generates valid mock binary image data with appropriate magic bytes."""
    if format_type in ("jpg", "jpeg"):
        # JPEG SOI marker \xff\xd8\xff\xe0
        content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    elif format_type == "png":
        # PNG signature
        content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    elif format_type == "webp":
        # RIFF header with WEBP marker
        content = b"RIFF\x24\x00\x00\x00WEBPVP8 "
    else:
        content = b"INVALID DATA"

    if len(content) < size_bytes:
        content += b"\x00" * (size_bytes - len(content))
    return content[:size_bytes]


class TestResolutionProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.DATABASE_URL = ""
        config.DATABASE = TEST_RES_DB
        config.SUPABASE_URL = ""
        config.SUPABASE_SERVICE_ROLE_KEY = ""
        if os.path.exists(TEST_RES_DB):
            try:
                os.remove(TEST_RES_DB)
            except Exception:
                pass
        init_database()
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_RES_DB):
            try:
                os.remove(TEST_RES_DB)
            except Exception:
                pass

    def setUp(self):
        config.SUPABASE_URL = ""
        config.SUPABASE_SERVICE_ROLE_KEY = ""
        conn = get_db_connection()
        conn.execute("DELETE FROM complaint_history")
        conn.execute("DELETE FROM notifications")
        conn.execute("DELETE FROM complaints")
        conn.execute("DELETE FROM students")
        conn.execute("DELETE FROM admin")

        # Seed students
        conn.execute(
            """
            INSERT INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (1, 'Resolution Student 1', 'S21001', 's21001@rguktong.ac.in', '9876543210', 'Hostel A', '101', 'pw1')
            """
        )
        conn.execute(
            """
            INSERT INTO students (id, name, id_no, email, phone, hostel, room_no, password)
            VALUES (2, 'Resolution Student 2', 'S21002', 's21002@rguktong.ac.in', '9876543211', 'Hostel B', '102', 'pw2')
            """
        )
        # Seed complaint
        conn.execute(
            """
            INSERT INTO complaints (id, student_id, category, title, description, priority, status, image)
            VALUES (1, 1, 'Plumbing', 'Leaking bathroom pipe', 'Water dripping continuously', 'High', 'Pending', '/static/uploads/complaints/1/orig.jpg')
            """
        )
        conn.commit()
        conn.close()

    def set_admin_session(self):
        with self.client.session_transaction() as sess:
            sess["admin"] = "admin"

    def set_student_session(self, student_id=1):
        with self.client.session_transaction() as sess:
            sess["student_logged_in"] = True
            sess["student_id"] = student_id
            sess["student_name"] = f"Student {student_id}"

    # 1. Admin resolve requires proof image
    def test_01_admin_resolve_requires_proof_image(self):
        self.set_admin_session()
        response = self.client.post(
            "/update_status/1",
            data={
                "status": "Resolved",
                "assigned_to": "Plumber Kumar",
                "remarks": "Issue fixed"
            },
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"resolution proof image is required", response.data)

        # Confirm complaint status in database is still Pending
        conn = get_db_connection()
        row = conn.execute("SELECT status, resolution_image FROM complaints WHERE id=1").fetchone()
        conn.close()
        self.assertEqual(row["status"], "Pending")
        self.assertIsNone(row["resolution_image"])

    # 2. Admin resolve success with valid JPG, PNG, and WEBP images
    def test_02_admin_resolve_success_with_jpg(self):
        self.set_admin_session()
        jpg_data = create_mock_image("jpg", 2048)
        file_obj = (io.BytesIO(jpg_data), "repair_proof.jpg")

        response = self.client.post(
            "/update_status/1",
            data={
                "status": "Resolved",
                "assigned_to": "Plumber Kumar",
                "remarks": "Pipe replaced with new fitting",
                "resolution_remarks": "Fixed leak with Teflon tape and new valve",
                "resolution_image": file_obj
            },
            content_type="multipart/form-data",
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Complaint Updated Successfully", response.data)

        conn = get_db_connection()
        c = conn.execute("SELECT * FROM complaints WHERE id=1").fetchone()
        hist = conn.execute("SELECT * FROM complaint_history WHERE complaint_id=1 AND status='Resolved'").fetchone()
        notif = conn.execute("SELECT * FROM notifications WHERE student_id=1").fetchone()
        conn.close()

        self.assertEqual(c["status"], "Resolved")
        self.assertIsNotNone(c["resolution_image"])
        self.assertIn("resolution_proofs/1/", c["resolution_image"])
        self.assertTrue(c["resolution_image"].endswith(".jpg"))
        self.assertIsNotNone(c["resolved_at"])
        self.assertEqual(c["assigned_to"], "Plumber Kumar")
        self.assertEqual(c["resolution_remarks"], "Fixed leak with Teflon tape and new valve")
        self.assertIsNotNone(hist)
        self.assertIsNotNone(notif)
        self.assertIn("Resolved", notif["message"])

    def test_03_admin_resolve_success_with_png(self):
        self.set_admin_session()
        png_data = create_mock_image("png", 3000)
        file_obj = (io.BytesIO(png_data), "fixed.png")

        response = self.client.post(
            "/update_status/1",
            data={
                "status": "Resolved",
                "assigned_to": "Plumber Kumar",
                "resolution_image": file_obj
            },
            content_type="multipart/form-data",
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

        conn = get_db_connection()
        c = conn.execute("SELECT * FROM complaints WHERE id=1").fetchone()
        conn.close()
        self.assertEqual(c["status"], "Resolved")
        self.assertTrue(c["resolution_image"].endswith(".png"))

    def test_04_admin_resolve_success_with_webp(self):
        self.set_admin_session()
        webp_data = create_mock_image("webp", 2500)
        file_obj = (io.BytesIO(webp_data), "fixed.webp")

        response = self.client.post(
            "/update_status/1",
            data={
                "status": "Resolved",
                "assigned_to": "Plumber Kumar",
                "resolution_image": file_obj
            },
            content_type="multipart/form-data",
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

        conn = get_db_connection()
        c = conn.execute("SELECT * FROM complaints WHERE id=1").fetchone()
        conn.close()
        self.assertEqual(c["status"], "Resolved")
        self.assertTrue(c["resolution_image"].endswith(".webp"))

    # 3. Invalid image formats rejected
    def test_05_invalid_image_formats_rejected(self):
        self.set_admin_session()
        # Invalid extension .txt
        txt_file = (io.BytesIO(b"Hello world"), "notes.txt")
        res1 = self.client.post(
            "/update_status/1",
            data={"status": "Resolved", "resolution_image": txt_file},
            content_type="multipart/form-data",
            follow_redirects=True
        )
        self.assertIn(b"Invalid resolution proof filename", res1.data)

        # Fake extension .jpg with text content
        fake_jpg = (io.BytesIO(b"plain text content not jpg"), "fake.jpg")
        res2 = self.client.post(
            "/update_status/1",
            data={"status": "Resolved", "resolution_image": fake_jpg},
            content_type="multipart/form-data",
            follow_redirects=True
        )
        self.assertIn(b"does not match its file type", res2.data)

    # 4. Images larger than 5 MB rejected
    def test_06_file_larger_than_5mb_rejected(self):
        self.set_admin_session()
        large_data = create_mock_image("jpg", 6 * 1024 * 1024) # 6 MB
        large_file = (io.BytesIO(large_data), "too_large.jpg")

        # Direct validator check
        with self.assertRaises(ValueError) as ctx:
            _validate_content(io.BytesIO(large_data), "jpg")
        self.assertIn("exceeds the maximum allowed size", str(ctx.exception))

        # HTTP request check (rejected by Flask MAX_CONTENT_LENGTH or route validator)
        response = self.client.post(
            "/update_status/1",
            data={"status": "Resolved", "resolution_image": large_file},
            content_type="multipart/form-data",
            follow_redirects=True
        )
        self.assertTrue(response.status_code == 413 or b"exceeds the maximum allowed size" in response.data)

    # 5. Pending and In Progress do NOT require proof
    def test_07_pending_and_inprogress_do_not_require_proof(self):
        self.set_admin_session()

        # Update to In Progress without image
        res_progress = self.client.post(
            "/update_status/1",
            data={"status": "In Progress", "assigned_to": "Technician Ramesh", "remarks": "Inspecting tap"},
            follow_redirects=True
        )
        self.assertEqual(res_progress.status_code, 200)

        conn = get_db_connection()
        c1 = conn.execute("SELECT status, assigned_to, resolution_image FROM complaints WHERE id=1").fetchone()
        self.assertEqual(c1["status"], "In Progress")
        self.assertEqual(c1["assigned_to"], "Technician Ramesh")
        self.assertIsNone(c1["resolution_image"])

        # Update to Pending without image
        res_pending = self.client.post(
            "/update_status/1",
            data={"status": "Pending", "assigned_to": "", "remarks": "Waiting for parts"},
            follow_redirects=True
        )
        self.assertEqual(res_pending.status_code, 200)

        c2 = conn.execute("SELECT status FROM complaints WHERE id=1").fetchone()
        conn.close()
        self.assertEqual(c2["status"], "Pending")

    # 6. Student can view proof for own resolved complaint
    def test_08_student_can_view_proof_for_own_complaint(self):
        # First resolve complaint 1 with proof
        conn = get_db_connection()
        conn.execute(
            """
            UPDATE complaints
            SET status='Resolved', resolution_image='/static/uploads/resolution_proofs/1/resolved.jpg',
                resolved_at='2026-10-31 12:00:00', resolution_remarks='Replaced valve with copper connector'
            WHERE id=1
            """
        )
        conn.commit()
        conn.close()

        # Student 1 logs in and views complaint 1
        self.set_student_session(student_id=1)
        response = self.client.get("/complaint/1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Resolution Proof Submitted by Administration", response.data)
        self.assertIn(b"/static/uploads/resolution_proofs/1/resolved.jpg", response.data)
        self.assertIn(b"2026-10-31 12:00:00", response.data)
        self.assertIn(b"Replaced valve with copper connector", response.data)
        self.assertIn(b"Open Original Image", response.data)

    # 7. Student cannot access another student's complaint proof
    def test_09_other_student_cannot_view_complaint_proof(self):
        # Student 2 logs in and attempts to view Student 1's complaint
        self.set_student_session(student_id=2)
        response = self.client.get("/complaint/1", follow_redirects=True)
        # Should redirect to complaints list with flash error
        self.assertIn(b"Complaint Not Found", response.data)
        self.assertNotIn(b"Resolution Proof Submitted by Administration", response.data)

    # 8. Resolution proof section omitted when status is Pending or no proof exists
    def test_10_resolution_proof_section_omitted_when_not_resolved(self):
        self.set_student_session(student_id=1)
        response = self.client.get("/complaint/1")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Resolution Proof Submitted by Administration", response.data)

    # 9. Original complaint photo evidence remains intact
    def test_11_original_complaint_image_unaffected(self):
        self.set_admin_session()
        jpg_data = create_mock_image("jpg", 2048)
        file_obj = (io.BytesIO(jpg_data), "repair.jpg")

        self.client.post(
            "/update_status/1",
            data={"status": "Resolved", "resolution_image": file_obj},
            content_type="multipart/form-data",
            follow_redirects=True
        )

        conn = get_db_connection()
        c = conn.execute("SELECT image, resolution_image FROM complaints WHERE id=1").fetchone()
        conn.close()
        # Original image must not be overwritten
        self.assertEqual(c["image"], "/static/uploads/complaints/1/orig.jpg")
        self.assertIn("resolution_proofs/1/", c["resolution_image"])

    # 10. Existing proof retention and replacement
    def test_12_existing_proof_retained_and_replaceable(self):
        self.set_admin_session()

        # Step A: Resolve with proof 1
        img1 = (io.BytesIO(create_mock_image("jpg", 1024)), "proof1.jpg")
        self.client.post(
            "/update_status/1",
            data={"status": "Resolved", "resolution_image": img1},
            content_type="multipart/form-data",
            follow_redirects=True
        )
        conn = get_db_connection()
        c1 = conn.execute("SELECT resolution_image FROM complaints WHERE id=1").fetchone()
        img1_ref = c1["resolution_image"]

        # Step B: Update again without new file: retains existing proof
        self.client.post(
            "/update_status/1",
            data={"status": "Resolved", "remarks": "Updated note"},
            follow_redirects=True
        )
        c2 = conn.execute("SELECT resolution_image, remarks FROM complaints WHERE id=1").fetchone()
        self.assertEqual(c2["resolution_image"], img1_ref)
        self.assertEqual(c2["remarks"], "Updated note")

        # Step C: Replace with proof 2
        img2 = (io.BytesIO(create_mock_image("png", 1024)), "proof2.png")
        self.client.post(
            "/update_status/1",
            data={"status": "Resolved", "resolution_image": img2},
            content_type="multipart/form-data",
            follow_redirects=True
        )
        c3 = conn.execute("SELECT resolution_image, remarks FROM complaints WHERE id=1").fetchone()
        conn.close()
        self.assertNotEqual(c3["resolution_image"], img1_ref)
        self.assertTrue(c3["resolution_image"].endswith(".png"))

    # 11. SQLite migration idempotency
    def test_13_sqlite_migration_idempotent(self):
        conn = get_db_connection()
        # Call migrate_sqlite multiple times to ensure safety
        migrate_sqlite(conn)
        migrate_sqlite(conn)
        cursor = conn.execute("PRAGMA table_info(complaints)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()

        self.assertIn("resolution_image", columns)
        self.assertIn("resolved_at", columns)
        self.assertIn("resolution_remarks", columns)

    # 12. Transaction rollback cleans up newly uploaded file
    def test_14_transaction_failure_cleans_up_uploaded_file(self):
        self.set_admin_session()
        jpg_data = create_mock_image("jpg", 2048)
        file_obj = (io.BytesIO(jpg_data), "fail_test.jpg")

        with patch("backend.routes.charan.update_status.get_db_connection") as mock_get_conn:
            # Simulate a DB connection where execute fails
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = [
                # First execute in complaint fetch
                MagicMock(fetchone=lambda: {"id": 1, "student_id": 1, "status": "Pending", "resolution_image": None, "resolved_at": None, "resolution_remarks": None, "title": "Test"}),
                # Second execute fails (UPDATE complaints)
                Exception("Database disk I/O error")
            ]
            mock_get_conn.return_value = mock_conn

            with patch("backend.services.storage_service.delete_from_cloud_storage") as mock_delete:
                response = self.client.post(
                    "/update_status/1",
                    data={"status": "Resolved", "resolution_image": file_obj},
                    content_type="multipart/form-data",
                    follow_redirects=False
                )
                self.assertEqual(response.status_code, 302)
                # Verify delete_from_cloud_storage was called to clean up the uploaded file
                self.assertTrue(mock_delete.called)


if __name__ == "__main__":
    unittest.main()
