from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from datetime import datetime, timedelta
import os
import io
import uuid
import subprocess
import sys
import secrets
import hashlib
import smtplib
import requests
import re
from email.message import EmailMessage

import config
from database.db import get_db_connection
from ml_engine import predict_complaint, find_duplicate

app = Flask(__name__)

app.config.update(
    SECRET_KEY=config.SECRET_KEY,
    UPLOAD_FOLDER=config.UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=config.MAX_CONTENT_LENGTH,
    ALLOWED_EXTENSIONS=config.ALLOWED_EXTENSIONS,
)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

COLLEGE_DOMAIN = "@rguktong.ac.in"
COLLEGE_NAME = "RGUKT Ongole"


def init_database():
    script = os.path.join(
        os.path.dirname(__file__),
        "database",
        "create_db.py"
    )
    subprocess.run(
        [sys.executable, script],
        check=True
    )


init_database()


def is_college_email(email):
    email = (email or "").strip().lower()

    return (
        email.count("@") == 1
        and email.endswith(COLLEGE_DOMAIN)
    )


def is_valid_id(id_no):
    return bool(
        re.fullmatch(
            r"O\d{6}",
            (id_no or "").strip().upper()
        )
    )


def hash_reset_token(token):
    return hashlib.sha256(
        token.encode()
    ).hexdigest()


def send_otp_email(recipient, otp):
    msg = EmailMessage()

    msg["Subject"] = (
        "RGUKT Ongole Hostel Complaint Portal - "
        "Password Reset OTP"
    )

    msg["From"] = config.MAIL_FROM
    msg["To"] = recipient

    msg.set_content(
        f"Your {COLLEGE_NAME} Hostel Complaint Portal "
        f"password reset OTP is: {otp}\n\n"
        f"This OTP expires in "
        f"{config.OTP_EXPIRY_MINUTES} minutes and can "
        f"be used only once.\n\n"
        "If you did not request this password reset, "
        "please ignore this email."
    )

    if (
        not config.SMTP_USERNAME
        or not config.SMTP_PASSWORD
        or not config.MAIL_FROM
    ):
        raise RuntimeError(
            "SMTP_USERNAME, SMTP_PASSWORD and "
            "MAIL_FROM must be configured in .env"
        )

    if config.SMTP_USE_TLS:

        with smtplib.SMTP(
            config.SMTP_HOST,
            config.SMTP_PORT,
            timeout=20
        ) as smtp:

            smtp.starttls()

            smtp.login(
                config.SMTP_USERNAME,
                config.SMTP_PASSWORD
            )

            smtp.send_message(msg)

    else:

        with smtplib.SMTP_SSL(
            config.SMTP_HOST,
            config.SMTP_PORT,
            timeout=20
        ) as smtp:

            smtp.login(
                config.SMTP_USERNAME,
                config.SMTP_PASSWORD
            )

            smtp.send_message(msg)


def upload_to_cloud_storage(
    file_obj,
    original_name,
    student_id
):
    if not config.SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL is not configured."
        )

    if not config.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not configured."
        )

    if not config.SUPABASE_STORAGE_BUCKET:
        raise RuntimeError(
            "SUPABASE_STORAGE_BUCKET is not configured."
        )

    if not original_name or "." not in original_name:
        raise ValueError(
            "Invalid attachment filename."
        )

    ext = original_name.rsplit(
        ".",
        1
    )[1].lower()

    object_path = (
        f"complaints/{student_id}/"
        f"{uuid.uuid4().hex}.{ext}"
    )

    url = (
        f"{config.SUPABASE_URL.rstrip('/')}"
        f"/storage/v1/object/"
        f"{config.SUPABASE_STORAGE_BUCKET}/"
        f"{object_path}"
    )

    content_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "pdf": "application/pdf"
    }

    content_type = content_types.get(
        ext,
        "application/octet-stream"
    )

    file_obj.seek(0)

    data = file_obj.read()

    response = requests.post(
        url,
        headers={
            "Authorization":
                f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}",

            "apikey":
                config.SUPABASE_SERVICE_ROLE_KEY,

            "Content-Type":
                content_type,

            "x-upsert":
                "false"
        },
        data=data,
        timeout=30
    )

    if not response.ok:
        raise RuntimeError(
            f"Supabase Storage upload failed "
            f"({response.status_code}): "
            f"{response.text[:500]}"
        )

    return (
        f"{config.SUPABASE_URL.rstrip('/')}"
        f"/storage/v1/object/public/"
        f"{config.SUPABASE_STORAGE_BUCKET}/"
        f"{object_path}"
    )


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in app.config["ALLOWED_EXTENSIONS"]
    )


def student_required():
    return "student_id" in session


def admin_required():
    return "admin" in session


def complaint_for_student(
    conn,
    complaint_id
):
    return conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE id=?
        AND student_id=?
        """,
        (
            complaint_id,
            session["student_id"]
        )
    ).fetchone()


def unread_count():

    if "student_id" not in session:
        return 0

    conn = get_db_connection()

    value = conn.execute(
        """
        SELECT COUNT(*)
        FROM notifications
        WHERE student_id=?
        AND is_read=0
        """,
        (
            session["student_id"],
        )
    ).fetchone()[0]

    conn.close()

    return value


@app.context_processor
def inject_globals():
    return {
        "unread_notifications":
            unread_count(),

        "college_name":
            COLLEGE_NAME
    }


@app.route("/")
def home():
    return render_template(
        "index.html"
    )


@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        id_no = request.form.get(
            "id_no",
            ""
        ).strip().upper()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        hostel = request.form.get(
            "hostel",
            ""
        ).strip()

        room = request.form.get(
            "room",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm = request.form.get(
            "confirm_password",
            ""
        )

        if not all([
            name,
            id_no,
            email,
            password
        ]):

            flash(
                "Please fill all required fields.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        if not is_valid_id(id_no):

            flash(
                "Invalid ID Number. Use format O221168.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        if not is_college_email(email):

            flash(
                "Only RGUKT Ongole college email addresses are allowed.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        expected_email = (
            id_no.lower()
            + "@rguktong.ac.in"
        )

        if email != expected_email:

            flash(
                "ID Number and college email do not match.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        if password != confirm:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        conn = get_db_connection()

        try:

            existing_id = conn.execute(
                """
                SELECT 1
                FROM students
                WHERE id_no=?
                """,
                (id_no,)
            ).fetchone()

            if existing_id:

                flash(
                    "ID Number Already Exists.",
                    "warning"
                )

                return redirect(
                    url_for("register")
                )

            existing_email = conn.execute(
                """
                SELECT 1
                FROM students
                WHERE lower(email)=?
                """,
                (email,)
            ).fetchone()

            if existing_email:

                flash(
                    "Email Already Exists.",
                    "warning"
                )

                return redirect(
                    url_for("register")
                )

            conn.execute(
                """
                INSERT INTO students(
                    name,
                    id_no,
                    email,
                    phone,
                    hostel,
                    room_no,
                    password
                )
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    name,
                    id_no,
                    email,
                    phone,
                    hostel,
                    room,
                    generate_password_hash(password)
                )
            )

            conn.commit()

        except Exception:

            conn.rollback()

            raise

        finally:

            conn.close()

        flash(
            "Registration Successful.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if "admin" in session:
        return redirect(
            url_for("admin_dashboard")
        )

    if request.method == "POST":

        id_no = request.form.get(
            "id_no",
            ""
        ).strip().upper()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db_connection()

        student = conn.execute(
            """
            SELECT *
            FROM students
            WHERE id_no=?
            """,
            (id_no,)
        ).fetchone()

        conn.close()

        if (
            student
            and check_password_hash(
                student["password"],
                password
            )
        ):

            session.clear()

            session["student_id"] = (
                student["id"]
            )

            session["student_name"] = (
                student["name"]
            )

            session["id_no"] = (
                student["id_no"]
            )

            session["email"] = (
                student["email"]
            )

            flash(
                "Login Successful.",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid ID Number or Password.",
            "danger"
        )

    return render_template(
        "login.html"
    )


@app.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        conn = get_db_connection()

        student = conn.execute(
            """
            SELECT id,email
            FROM students
            WHERE lower(email)=?
            """,
            (email,)
        ).fetchone()

        if student:

            otp = (
                f"{secrets.randbelow(1000000):06d}"
            )

            otp_hash = hash_reset_token(
                otp
            )

            expires_at = (
                datetime.utcnow()
                + timedelta(
                    minutes=config.OTP_EXPIRY_MINUTES
                )
            ).isoformat()

            conn.execute(
                """
                DELETE FROM password_reset_otps
                WHERE student_id=?
                """,
                (student["id"],)
            )

            conn.execute(
                """
                INSERT INTO password_reset_otps(
                    student_id,
                    otp_hash,
                    expires_at,
                    attempts,
                    verified
                )
                VALUES(?,?,?,0,0)
                """,
                (
                    student["id"],
                    otp_hash,
                    expires_at
                )
            )

            conn.commit()

            try:

                send_otp_email(
                    student["email"],
                    otp
                )

            except Exception as exc:

                conn.execute(
                    """
                    DELETE FROM password_reset_otps
                    WHERE student_id=?
                    """,
                    (student["id"],)
                )

                conn.commit()
                conn.close()

                app.logger.exception(
                    "OTP email failed"
                )

                if app.debug:

                    flash(
                        f"Unable to send OTP: {exc}",
                        "danger"
                    )

                else:

                    flash(
                        "Unable to send the reset OTP right now. Please check the SMTP settings and try again.",
                        "danger"
                    )

                return redirect(
                    url_for("forgot_password")
                )

            conn.close()

            session["reset_student_id"] = (
                student["id"]
            )

            session["reset_email"] = (
                student["email"]
            )

            flash(
                "A 6-digit OTP has been sent to your registered email.",
                "success"
            )

            return redirect(
                url_for("verify_reset_otp")
            )

        conn.close()

        flash(
            "If an account exists for that email, an OTP has been sent.",
            "success"
        )

    return render_template(
        "forgot_password.html"
    )


@app.route(
    "/verify-reset-otp",
    methods=["GET", "POST"]
)
def verify_reset_otp():

    if "reset_student_id" not in session:

        return redirect(
            url_for("forgot_password")
        )

    if request.method == "POST":

        otp = request.form.get(
            "otp",
            ""
        ).strip()

        if (
            not otp.isdigit()
            or len(otp) != 6
        ):

            flash(
                "Enter a valid 6-digit OTP.",
                "danger"
            )

            return redirect(
                url_for("verify_reset_otp")
            )

        conn = get_db_connection()

        row = conn.execute(
            """
            SELECT *
            FROM password_reset_otps
            WHERE student_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                session["reset_student_id"],
            )
        ).fetchone()

        if not row:

            conn.close()

            flash(
                "OTP not found. Request a new OTP.",
                "danger"
            )

            return redirect(
                url_for("forgot_password")
            )

        if row["attempts"] >= config.OTP_MAX_ATTEMPTS:

            conn.close()

            flash(
                "Too many incorrect attempts. Request a new OTP.",
                "danger"
            )

            return redirect(
                url_for("forgot_password")
            )

        try:

            valid_time = (
                datetime.fromisoformat(
                    str(row["expires_at"])
                )
                > datetime.utcnow()
            )

        except ValueError:

            valid_time = False

        if not valid_time:

            conn.close()

            flash(
                "OTP has expired. Request a new OTP.",
                "danger"
            )

            return redirect(
                url_for("forgot_password")
            )

        if hash_reset_token(otp) != row["otp_hash"]:

            conn.execute(
                """
                UPDATE password_reset_otps
                SET attempts=attempts+1
                WHERE id=?
                """,
                (row["id"],)
            )

            conn.commit()
            conn.close()

            flash(
                "Incorrect OTP. Please try again.",
                "danger"
            )

            return redirect(
                url_for("verify_reset_otp")
            )

        conn.execute(
            """
            UPDATE password_reset_otps
            SET verified=1
            WHERE id=?
            """,
            (row["id"],)
        )

        conn.commit()
        conn.close()

        session["reset_verified"] = True

        return redirect(
            url_for("reset_password")
        )

    return render_template(
        "verify_reset_otp.html",
        email=session.get("reset_email")
    )


@app.route(
    "/reset-password",
    methods=["GET", "POST"]
)
def reset_password():

    if (
        not session.get("reset_verified")
        or not session.get("reset_student_id")
    ):

        return redirect(
            url_for("forgot_password")
        )

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm = request.form.get(
            "confirm_password",
            ""
        )

        if len(password) < 8:

            flash(
                "Password must contain at least 8 characters.",
                "danger"
            )

            return redirect(
                url_for("reset_password")
            )

        if password != confirm:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("reset_password")
            )

        conn = get_db_connection()

        conn.execute(
            """
            UPDATE students
            SET password=?
            WHERE id=?
            """,
            (
                generate_password_hash(password),
                session["reset_student_id"]
            )
        )

        conn.execute(
            """
            DELETE FROM password_reset_otps
            WHERE student_id=?
            """,
            (
                session["reset_student_id"],
            )
        )

        conn.commit()
        conn.close()

        session.pop(
            "reset_student_id",
            None
        )

        session.pop(
            "reset_email",
            None
        )

        session.pop(
            "reset_verified",
            None
        )

        flash(
            "Password reset successfully. You can now log in.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "reset_password.html"
    )


@app.route("/logout")
def logout():

    session.clear()

    flash(
        "Logged Out Successfully.",
        "success"
    )

    return redirect(
        url_for("login")
    )


@app.route("/dashboard")
def dashboard():

    if not student_required():
        return redirect(
            url_for("login")
        )

    sid = session["student_id"]

    conn = get_db_connection()

    total = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE student_id=?
        """,
        (sid,)
    ).fetchone()[0]

    pending = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE student_id=?
        AND status='Pending'
        """,
        (sid,)
    ).fetchone()[0]

    progress = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE student_id=?
        AND status='In Progress'
        """,
        (sid,)
    ).fetchone()[0]

    resolved = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE student_id=?
        AND status='Resolved'
        """,
        (sid,)
    ).fetchone()[0]

    recent = conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE student_id=?
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (sid,)
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        total=total,
        pending=pending,
        progress=progress,
        resolved=resolved,
        recent=recent
    )


@app.route(
    "/add_complaint",
    methods=["GET", "POST"]
)
def add_complaint():

    if not student_required():
        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        category = request.form.get(
            "category",
            ""
        ).strip()

        priority = request.form.get(
            "priority",
            ""
        ).strip()

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        if not all([
            category,
            priority,
            title,
            description
        ]):

            flash(
                "Category, priority, title and description are required.",
                "danger"
            )

            return redirect(
                url_for("add_complaint")
            )

        filename = ""

        image = request.files.get(
            "image"
        )

        if image and image.filename:

            if not allowed_file(
                image.filename
            ):

                flash(
                    "Only PNG, JPG and JPEG images are allowed.",
                    "danger"
                )

                return redirect(
                    url_for("add_complaint")
                )

            try:

                filename = upload_to_cloud_storage(
                    image,
                    secure_filename(
                        image.filename
                    ),
                    session["student_id"]
                )

            except Exception:

                app.logger.exception(
                    "Complaint attachment upload failed"
                )

                flash(
                    "Complaint image upload failed. Please check Supabase Storage settings and try again.",
                    "danger"
                )

                return redirect(
                    url_for("add_complaint")
                )

        conn = get_db_connection()

        existing = conn.execute(
            """
            SELECT
                id,
                title,
                description,
                status
            FROM complaints
            """
        ).fetchall()

        ai = predict_complaint(
            title,
            description,
            category,
            priority
        )

        duplicate = find_duplicate(
            title,
            description,
            existing
        )

        duplicate_id = (
            duplicate["id"]
            if duplicate
            else None
        )

        duplicate_similarity = (
            duplicate["similarity"]
            if duplicate
            else None
        )

        insert_sql = """
            INSERT INTO complaints(
                student_id,
                category,
                title,
                description,
                image,
                priority,
                status,
                ai_category,
                ai_category_confidence,
                ai_priority,
                ai_priority_confidence,
                ai_resolution_days,
                ai_duplicate_id,
                ai_duplicate_similarity
            )
            VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
        """

        if config.DATABASE_URL:
            insert_sql += " RETURNING id"

        cur = conn.execute(
            insert_sql,
            (
                session["student_id"],
                category,
                title,
                description,
                filename,
                priority,
                "Pending",
                ai["predicted_category"],
                ai["category_confidence"],
                ai["predicted_priority"],
                ai["priority_confidence"],
                ai["resolution_days"],
                duplicate_id,
                duplicate_similarity
            )
        )

        if config.DATABASE_URL:

            complaint_id = (
                cur.fetchone()["id"]
            )

        else:

            complaint_id = cur.lastrowid

        conn.execute(
            """
            INSERT INTO complaint_history(
                complaint_id,
                status
            )
            VALUES(?,?)
            """,
            (
                complaint_id,
                "Pending"
            )
        )

        conn.commit()
        conn.close()

        if duplicate:

            flash(
                f"Complaint submitted. Possible duplicate #{duplicate_id} detected ({duplicate_similarity}% similarity).",
                "warning"
            )

        else:

            flash(
                f"Complaint submitted. AI estimated resolution time: {ai['resolution_days']} days.",
                "success"
            )

        return redirect(
            url_for(
                "view_complaint",
                id=complaint_id
            )
        )

    return render_template(
        "add_complaint.html"
    )


@app.route("/complaints")
def complaints():

    if not student_required():
        return redirect(
            url_for("login")
        )

    search = request.args.get(
        "search",
        ""
    ).strip()

    status = request.args.get(
        "status",
        ""
    ).strip()

    conn = get_db_connection()

    query = """
        SELECT *
        FROM complaints
        WHERE student_id=?
    """

    params = [
        session["student_id"]
    ]

    if search:

        query += """
            AND (
                title LIKE ?
                OR description LIKE ?
                OR category LIKE ?
            )
        """

        q = f"%{search}%"

        params += [
            q,
            q,
            q
        ]

    if status:

        query += """
            AND status=?
        """

        params.append(
            status
        )

    query += """
        ORDER BY created_at DESC
    """

    data = conn.execute(
        query,
        params
    ).fetchall()

    conn.close()

    return render_template(
        "complaint_history.html",
        complaints=data
    )


@app.route(
    "/delete_complaint/<int:id>",
    methods=["POST"]
)
def delete_complaint(id):

    if not student_required():
        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    complaint = complaint_for_student(
        conn,
        id
    )

    if not complaint:

        conn.close()

        flash(
            "Complaint Not Found.",
            "danger"
        )

        return redirect(
            url_for("complaints")
        )

    if complaint["status"] == "Resolved":

        conn.close()

        flash(
            "Resolved complaints cannot be deleted.",
            "warning"
        )

        return redirect(
            url_for("complaints")
        )

    conn.execute(
        """
        DELETE FROM complaints
        WHERE id=?
        AND student_id=?
        """,
        (
            id,
            session["student_id"]
        )
    )

    conn.commit()
    conn.close()

    flash(
        "Complaint Deleted Successfully.",
        "success"
    )

    return redirect(
        url_for("complaints")
    )


@app.route(
    "/profile",
    methods=["GET", "POST"]
)
def profile():

    if not student_required():
        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        hostel = request.form.get(
            "hostel",
            ""
        ).strip()

        room = request.form.get(
            "room_no",
            ""
        ).strip()

        if not is_college_email(email):

            flash(
                "Only RGUKT Ongole college email addresses are allowed.",
                "danger"
            )

        else:

            try:

                conn.execute(
                    """
                    UPDATE students
                    SET name=?,
                        email=?,
                        phone=?,
                        hostel=?,
                        room_no=?
                    WHERE id=?
                    """,
                    (
                        name,
                        email,
                        phone,
                        hostel,
                        room,
                        session["student_id"]
                    )
                )

                conn.commit()

                session["student_name"] = name
                session["email"] = email

                flash(
                    "Profile Updated Successfully.",
                    "success"
                )

            except Exception:

                conn.rollback()

                flash(
                    "Unable to update profile. Email may already be in use.",
                    "danger"
                )

    student = conn.execute(
        """
        SELECT *
        FROM students
        WHERE id=?
        """,
        (
            session["student_id"],
        )
    ).fetchone()

    conn.close()

    return render_template(
        "profile.html",
        student=student
    )


@app.route(
    "/change_password",
    methods=["GET", "POST"]
)
def change_password():

    if not student_required():
        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        old = request.form.get(
            "old_password",
            ""
        )

        new = request.form.get(
            "new_password",
            ""
        )

        confirm = request.form.get(
            "confirm_password",
            ""
        )

        if new != confirm:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("change_password")
            )

        if len(new) < 6:

            flash(
                "New password must contain at least 6 characters.",
                "danger"
            )

            return redirect(
                url_for("change_password")
            )

        conn = get_db_connection()

        student = conn.execute(
            """
            SELECT password
            FROM students
            WHERE id=?
            """,
            (
                session["student_id"],
            )
        ).fetchone()

        if (
            not student
            or not check_password_hash(
                student["password"],
                old
            )
        ):

            conn.close()

            flash(
                "Current password is incorrect.",
                "danger"
            )

            return redirect(
                url_for("change_password")
            )

        conn.execute(
            """
            UPDATE students
            SET password=?
            WHERE id=?
            """,
            (
                generate_password_hash(new),
                session["student_id"]
            )
        )

        conn.commit()
        conn.close()

        flash(
            "Password Updated Successfully.",
            "success"
        )

        return redirect(
            url_for("profile")
        )

    return render_template(
        "change_password.html"
    )


@app.route(
    "/admin_login",
    methods=["GET", "POST"]
)
def admin_login():

    if "student_id" in session:

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            username == config.ADMIN_USERNAME
            and password == config.ADMIN_PASSWORD
        ):

            session.clear()

            session["admin"] = username

            flash(
                "Admin Login Successful.",
                "success"
            )

            return redirect(
                url_for("admin_dashboard")
            )

        flash(
            "Invalid Username or Password.",
            "danger"
        )

    return render_template(
        "admin_login.html"
    )


@app.route("/admin_dashboard")
def admin_dashboard():

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    stats = {

        "total":
            conn.execute(
                "SELECT COUNT(*) FROM complaints"
            ).fetchone()[0],

        "pending":
            conn.execute(
                """
                SELECT COUNT(*)
                FROM complaints
                WHERE status='Pending'
                """
            ).fetchone()[0],

        "progress":
            conn.execute(
                """
                SELECT COUNT(*)
                FROM complaints
                WHERE status='In Progress'
                """
            ).fetchone()[0],

        "resolved":
            conn.execute(
                """
                SELECT COUNT(*)
                FROM complaints
                WHERE status='Resolved'
                """
            ).fetchone()[0],

        "high_ai":
            conn.execute(
                """
                SELECT COUNT(*)
                FROM complaints
                WHERE ai_priority='High'
                AND status!='Resolved'
                """
            ).fetchone()[0],

        "duplicates":
            conn.execute(
                """
                SELECT COUNT(*)
                FROM complaints
                WHERE ai_duplicate_id IS NOT NULL
                """
            ).fetchone()[0]
    }

    recent = conn.execute(
        """
        SELECT
            complaints.*,
            students.name,
            students.id_no
        FROM complaints
        JOIN students
        ON students.id=complaints.student_id
        ORDER BY complaints.created_at DESC
        LIMIT 8
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        **stats,
        recent=recent
    )


@app.route("/manage_complaints")
def manage_complaints():

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    page = max(
        1,
        request.args.get(
            "page",
            1,
            type=int
        )
    )

    per_page = 10

    offset = (
        page - 1
    ) * per_page

    search = request.args.get(
        "search",
        ""
    ).strip()

    status = request.args.get(
        "status",
        ""
    ).strip()

    priority = request.args.get(
        "priority",
        ""
    ).strip()

    date = request.args.get(
        "date",
        ""
    ).strip()

    conn = get_db_connection()

    where = [
        "1=1"
    ]

    params = []

    if search:

        where.append(
            """
            (
                students.name LIKE ?
                OR students.id_no LIKE ?
                OR complaints.title LIKE ?
                OR complaints.description LIKE ?
            )
            """
        )

        q = f"%{search}%"

        params += [
            q,
            q,
            q,
            q
        ]

    if status:

        where.append(
            "complaints.status=?"
        )

        params.append(
            status
        )

    if priority:

        where.append(
            "complaints.priority=?"
        )

        params.append(
            priority
        )

    if date:

        where.append(
            "DATE(complaints.created_at)=?"
        )

        params.append(
            date
        )

    where_sql = " AND ".join(
        where
    )

    total = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM complaints
        JOIN students
        ON students.id=complaints.student_id
        WHERE {where_sql}
        """,
        params
    ).fetchone()[0]

    rows = conn.execute(
        f"""
        SELECT
            complaints.*,
            students.name,
            students.id_no,
            students.hostel
        FROM complaints
        JOIN students
        ON students.id=complaints.student_id
        WHERE {where_sql}
        ORDER BY complaints.created_at DESC
        LIMIT ? OFFSET ?
        """,
        params + [
            per_page,
            offset
        ]
    ).fetchall()

    conn.close()

    pages = max(
        1,
        (total + per_page - 1)
        // per_page
    )

    return render_template(
        "manage_complaints.html",
        complaints=rows,
        page=page,
        pages=pages,
        total=total
    )


@app.route(
    "/update_status/<int:id>",
    methods=["GET", "POST"]
)
def update_status(id):

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    complaint = conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE id=?
        """,
        (id,)
    ).fetchone()

    if not complaint:

        conn.close()

        flash(
            "Complaint Not Found.",
            "danger"
        )

        return redirect(
            url_for("manage_complaints")
        )

    if request.method == "POST":

        status = request.form.get(
            "status",
            "Pending"
        )

        assigned = request.form.get(
            "assigned_to",
            ""
        ).strip()

        remarks = request.form.get(
            "remarks",
            ""
        ).strip()

        old_status = complaint["status"]

        conn.execute(
            """
            UPDATE complaints
            SET status=?,
                assigned_to=?,
                remarks=?
            WHERE id=?
            """,
            (
                status,
                assigned,
                remarks,
                id
            )
        )

        if old_status != status:

            conn.execute(
                """
                INSERT INTO complaint_history(
                    complaint_id,
                    status
                )
                VALUES(?,?)
                """,
                (
                    id,
                    status
                )
            )

            conn.execute(
                """
                INSERT INTO notifications(
                    student_id,
                    message
                )
                VALUES(?,?)
                """,
                (
                    complaint["student_id"],
                    f"Your complaint #{id} status changed to {status}."
                )
            )

        conn.commit()
        conn.close()

        flash(
            "Complaint Updated Successfully.",
            "success"
        )

        return redirect(
            url_for("manage_complaints")
        )

    history = conn.execute(
        """
        SELECT *
        FROM complaint_history
        WHERE complaint_id=?
        ORDER BY date DESC
        """,
        (id,)
    ).fetchall()

    conn.close()

    return render_template(
        "update_status.html",
        complaint=complaint,
        history=history
    )


@app.route("/admin_logout")
def admin_logout():

    session.clear()

    flash(
        "Admin Logged Out Successfully.",
        "success"
    )

    return redirect(
        url_for("admin_login")
    )


@app.route("/analytics")
def analytics():

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    monthly = conn.execute(
        """
        SELECT
            TO_CHAR(
                DATE_TRUNC(
                    'month',
                    created_at
                ),
                'YYYY-MM'
            ) AS month,
            COUNT(*) AS total
        FROM complaints
        GROUP BY month
        ORDER BY month
        """
    ).fetchall()

    category_data = conn.execute(
        """
        SELECT
            category,
            COUNT(*) AS total
        FROM complaints
        GROUP BY category
        ORDER BY total DESC
        """
    ).fetchall()

    status_rows = conn.execute(
        """
        SELECT
            status,
            COUNT(*) AS total
        FROM complaints
        GROUP BY status
        """
    ).fetchall()

    priority_rows = conn.execute(
        """
        SELECT
            priority,
            COUNT(*) AS total
        FROM complaints
        GROUP BY priority
        """
    ).fetchall()

    ai_rows = conn.execute(
        """
        SELECT
            ai_category,
            COUNT(*) AS total
        FROM complaints
        GROUP BY ai_category
        ORDER BY total DESC
        """
    ).fetchall()

    avg_resolution = conn.execute(
        """
        SELECT AVG(ai_resolution_days)
        FROM complaints
        WHERE ai_resolution_days IS NOT NULL
        """
    ).fetchone()[0] or 0

    duplicate_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE ai_duplicate_id IS NOT NULL
        """
    ).fetchone()[0]

    conn.close()

    status_map = {
        r["status"]:
            r["total"]
        for r in status_rows
    }

    priority_map = {
        r["priority"]:
            r["total"]
        for r in priority_rows
    }

    return render_template(
        "analytics.html",

        months=[
            r["month"]
            for r in monthly
        ],

        totals=[
            r["total"]
            for r in monthly
        ],

        categories=[
            r["category"]
            for r in category_data
        ],

        category_count=[
            r["total"]
            for r in category_data
        ],

        pending=status_map.get(
            "Pending",
            0
        ),

        progress=status_map.get(
            "In Progress",
            0
        ),

        resolved=status_map.get(
            "Resolved",
            0
        ),

        low=priority_map.get(
            "Low",
            0
        ),

        medium=priority_map.get(
            "Medium",
            0
        ),

        high=priority_map.get(
            "High",
            0
        ),

        ai_categories=[
            r["ai_category"]
            for r in ai_rows
        ],

        ai_category_count=[
            r["total"]
            for r in ai_rows
        ],

        avg_resolution=round(
            avg_resolution,
            1
        ),

        duplicate_count=duplicate_count
    )


@app.route("/complaint/<int:id>")
def view_complaint(id):

    if not student_required():
        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    complaint = complaint_for_student(
        conn,
        id
    )

    history = (
        conn.execute(
            """
            SELECT *
            FROM complaint_history
            WHERE complaint_id=?
            ORDER BY date ASC
            """,
            (id,)
        ).fetchall()
        if complaint
        else []
    )

    duplicate = None

    if (
        complaint
        and complaint["ai_duplicate_id"]
    ):

        duplicate = conn.execute(
            """
            SELECT
                id,
                title,
                status
            FROM complaints
            WHERE id=?
            """,
            (
                complaint["ai_duplicate_id"],
            )
        ).fetchone()

    conn.close()

    if not complaint:

        flash(
            "Complaint Not Found.",
            "danger"
        )

        return redirect(
            url_for("complaints")
        )

    return render_template(
        "view_complaint.html",
        complaint=complaint,
        history=history,
        duplicate=duplicate
    )


@app.route(
    "/edit_complaint/<int:id>",
    methods=["GET", "POST"]
)
def edit_complaint(id):

    if not student_required():
        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    complaint = complaint_for_student(
        conn,
        id
    )

    if not complaint:

        conn.close()

        flash(
            "Complaint Not Found.",
            "danger"
        )

        return redirect(
            url_for("complaints")
        )

    if complaint["status"] == "Resolved":

        conn.close()

        flash(
            "Resolved complaints cannot be edited.",
            "warning"
        )

        return redirect(
            url_for("complaints")
        )

    if request.method == "POST":

        category = request.form.get(
            "category",
            ""
        ).strip()

        priority = request.form.get(
            "priority",
            ""
        ).strip()

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        image_name = complaint["image"]

        image = request.files.get(
            "image"
        )

        if image and image.filename:

            if not allowed_file(
                image.filename
            ):

                conn.close()

                flash(
                    "Only PNG, JPG and JPEG images are allowed.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "edit_complaint",
                        id=id
                    )
                )

            try:

                image_name = upload_to_cloud_storage(
                    image,
                    secure_filename(
                        image.filename
                    ),
                    session["student_id"]
                )

            except Exception:

                conn.close()

                app.logger.exception(
                    "Complaint attachment upload failed during edit"
                )

                flash(
                    "Complaint image upload failed. Please check Supabase Storage settings and try again.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "edit_complaint",
                        id=id
                    )
                )

        existing = conn.execute(
            """
            SELECT
                id,
                title,
                description,
                status
            FROM complaints
            WHERE id!=?
            """,
            (id,)
        ).fetchall()

        ai = predict_complaint(
            title,
            description,
            category,
            priority
        )

        duplicate = find_duplicate(
            title,
            description,
            existing
        )

        conn.execute(
            """
            UPDATE complaints
            SET
                category=?,
                priority=?,
                title=?,
                description=?,
                image=?,
                ai_category=?,
                ai_category_confidence=?,
                ai_priority=?,
                ai_priority_confidence=?,
                ai_resolution_days=?,
                ai_duplicate_id=?,
                ai_duplicate_similarity=?
            WHERE id=?
            """,
            (
                category,
                priority,
                title,
                description,
                image_name,
                ai["predicted_category"],
                ai["category_confidence"],
                ai["predicted_priority"],
                ai["priority_confidence"],
                ai["resolution_days"],
                duplicate["id"]
                if duplicate
                else None,
                duplicate["similarity"]
                if duplicate
                else None,
                id
            )
        )

        conn.commit()
        conn.close()

        flash(
            "Complaint Updated Successfully with fresh AI analysis.",
            "success"
        )

        return redirect(
            url_for(
                "view_complaint",
                id=id
            )
        )

    conn.close()

    return render_template(
        "edit_complaint.html",
        complaint=complaint
    )


@app.route("/export_pdf")
def export_pdf():

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT
            complaints.*,
            students.name,
            students.id_no
        FROM complaints
        JOIN students
        ON complaints.student_id=students.id
        ORDER BY complaints.created_at DESC
        """
    ).fetchall()

    conn.close()

    buffer = io.BytesIO()

    pdf = canvas.Canvas(
        buffer
    )

    pdf.setTitle(
        "RGUKT Ongole Complaint Report"
    )

    y = 800

    pdf.setFont(
        "Helvetica-Bold",
        16
    )

    pdf.drawString(
        40,
        y,
        "RGUKT Ongole - Hostel Complaint Report"
    )

    y -= 30

    pdf.setFont(
        "Helvetica",
        9
    )

    for c in rows:

        line = (
            f"#{c['id']} | "
            f"{c['name']} | "
            f"{c['id_no']} | "
            f"{c['category']} | "
            f"{c['priority']} | "
            f"{c['status']} | "
            f"AI: "
            f"{c['ai_resolution_days'] or '-'}d"
        )

        pdf.drawString(
            40,
            y,
            line[:115]
        )

        y -= 16

        if y < 45:

            pdf.showPage()

            y = 800

            pdf.setFont(
                "Helvetica",
                9
            )

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="RGUKT_Ongole_Complaint_Report.pdf",
        mimetype="application/pdf"
    )


@app.route("/export_excel")
def export_excel():

    if not admin_required():
        return redirect(
            url_for("admin_login")
        )

    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT
            complaints.*,
            students.name,
            students.id_no,
            students.hostel
        FROM complaints
        JOIN students
        ON complaints.student_id=students.id
        ORDER BY complaints.created_at DESC
        """
    ).fetchall()

    conn.close()

    wb = Workbook()

    ws = wb.active

    ws.title = "Complaints"

    ws.append([
        "ID",
        "Student",
        "ID No",
        "Hostel",
        "Category",
        "Title",
        "Priority",
        "Status",
        "Assigned To",
        "AI Category",
        "AI Category Confidence",
        "AI Priority",
        "AI Priority Confidence",
        "AI Resolution Days",
        "Duplicate ID",
        "Similarity %",
        "Date"
    ])

    for c in rows:

        ws.append([
            c["id"],
            c["name"],
            c["id_no"],
            c["hostel"],
            c["category"],
            c["title"],
            c["priority"],
            c["status"],
            c["assigned_to"],
            c["ai_category"],
            c["ai_category_confidence"],
            c["ai_priority"],
            c["ai_priority_confidence"],
            c["ai_resolution_days"],
            c["ai_duplicate_id"],
            c["ai_duplicate_similarity"],
            c["created_at"]
        ])

    buffer = io.BytesIO()

    wb.save(
        buffer
    )

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="RGUKT_Ongole_Complaint_Report.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


@app.route("/notifications")
def notifications():

    if not student_required():
        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    data = conn.execute(
        """
        SELECT *
        FROM notifications
        WHERE student_id=?
        ORDER BY created_at DESC
        """,
        (
            session["student_id"],
        )
    ).fetchall()

    conn.close()

    return render_template(
        "notifications.html",
        notifications=data
    )


@app.route(
    "/notifications/read/<int:id>",
    methods=["POST"]
)
def notification_read(id):

    if not student_required():
        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    conn.execute(
        """
        UPDATE notifications
        SET is_read=1
        WHERE id=?
        AND student_id=?
        """,
        (
            id,
            session["student_id"]
        )
    )

    conn.commit()

    conn.close()

    return redirect(
        url_for("notifications")
    )


@app.route(
    "/notifications/read-all",
    methods=["POST"]
)
def notifications_read_all():

    if not student_required():
        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    conn.execute(
        """
        UPDATE notifications
        SET is_read=1
        WHERE student_id=?
        """,
        (
            session["student_id"],
        )
    )

    conn.commit()

    conn.close()

    return redirect(
        url_for("notifications")
    )


@app.route("/activity")
def activity():

    if not student_required():
        return redirect(
            url_for("login")
        )

    conn = get_db_connection()

    complaints_rows = conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE student_id=?
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (
            session["student_id"],
        )
    ).fetchall()

    history = conn.execute(
        """
        SELECT
            h.*,
            c.title
        FROM complaint_history h
        JOIN complaints c
        ON c.id=h.complaint_id
        WHERE c.student_id=?
        ORDER BY h.date DESC
        LIMIT 30
        """,
        (
            session["student_id"],
        )
    ).fetchall()

    conn.close()

    return render_template(
        "activity.html",
        complaints=complaints_rows,
        history=history
    )


@app.route(
    "/api/ai/analyze",
    methods=["POST"]
)
def ai_analyze():

    if not student_required():

        return jsonify({
            "error": "Unauthorized"
        }), 401

    payload = (
        request.get_json(
            silent=True
        )
        or {}
    )

    title = payload.get(
        "title",
        ""
    )

    description = payload.get(
        "description",
        ""
    )

    category = payload.get(
        "category",
        ""
    )

    priority = payload.get(
        "priority",
        ""
    )

    if not title or not description:

        return jsonify({
            "error":
                "Title and description are required"
        }), 400

    return jsonify(
        predict_complaint(
            title,
            description,
            category,
            priority
        )
    )


@app.errorhandler(404)
def page_not_found(e):

    return render_template(
        "404.html"
    ), 404


@app.errorhandler(500)
def server_error(e):

    return render_template(
        "500.html"
    ), 500


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=os.environ.get(
            "FLASK_DEBUG",
            "0"
        ) == "1"
    )