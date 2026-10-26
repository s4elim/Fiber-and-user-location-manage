import hmac
import json
import math
import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",
)
DB_NAME = "records.db"
AREAS = (
    "Kushtia",
    "Jhenaidah",
    "Pabna",
    "Dhaka",
    "Natore",
    "Sirajganj",
    "Ishwardi",
)


def init_db():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                work_type TEXT,
                latitude REAL,
                longitude REAL,
                accuracy REAL,
                start_meter REAL,
                end_meter REAL,
                total_fiber REAL,
                onu_id TEXT,
                customer_name TEXT,
                splitter_info TEXT,
                notes TEXT
            )
        """)
        existing_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(job_logs)")
        }
        if "customer_id" not in existing_columns:
            cursor.execute("ALTER TABLE job_logs ADD COLUMN customer_id TEXT")
        if "tj_details" not in existing_columns:
            cursor.execute("ALTER TABLE job_logs ADD COLUMN tj_details TEXT")
        if "location" not in existing_columns:
            cursor.execute("ALTER TABLE job_logs ADD COLUMN location TEXT")
        if "device_info" not in existing_columns:
            cursor.execute("ALTER TABLE job_logs ADD COLUMN device_info TEXT")
        if "status" not in existing_columns:
            cursor.execute(
                "ALTER TABLE job_logs ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"
            )
        if "completed_by" not in existing_columns:
            cursor.execute("ALTER TABLE job_logs ADD COLUMN completed_by TEXT")
        if "completed_at" not in existing_columns:
            cursor.execute("ALTER TABLE job_logs ADD COLUMN completed_at TEXT")
        if "area" not in existing_columns:
            cursor.execute("ALTER TABLE job_logs ADD COLUMN area TEXT")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('main', 'editor')),
                display_name TEXT NOT NULL DEFAULT '',
                mobile TEXT NOT NULL DEFAULT ''
            )
        """)
        account_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(admin_accounts)")
        }
        if "display_name" not in account_columns:
            cursor.execute(
                "ALTER TABLE admin_accounts ADD COLUMN display_name TEXT NOT NULL DEFAULT ''"
            )
        if "mobile" not in account_columns:
            cursor.execute(
                "ALTER TABLE admin_accounts ADD COLUMN mobile TEXT NOT NULL DEFAULT ''"
            )
        cursor.execute(
            "UPDATE admin_accounts SET display_name = username "
            "WHERE role = 'editor' AND display_name = ''"
        )
        main_admin = cursor.execute(
            "SELECT id FROM admin_accounts WHERE role = 'main' LIMIT 1"
        ).fetchone()
        if main_admin is None:
            admin_username = os.environ.get("ADMIN_USERNAME", "").strip()
            admin_password = os.environ.get("ADMIN_PASSWORD", "")
            if admin_username and valid_account_password(admin_password):
                cursor.execute(
                    """
                    INSERT INTO admin_accounts (username, password_hash, role)
                    VALUES (?, ?, 'main')
                    """,
                    (admin_username, generate_password_hash(admin_password)),
                )
        conn.commit()


def get_current_admin():
    account_id = session.get("admin_account_id")
    if not isinstance(account_id, int):
        return None

    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute(
            "SELECT id, username, role, display_name, mobile "
            "FROM admin_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
    if row is None:
        session.clear()
        return None
    return {
        "id": row[0],
        "username": row[1],
        "role": row[2],
        "display_name": row[3],
        "mobile": row[4],
    }


def valid_account_password(password):
    return isinstance(password, str) and 8 <= len(password) <= 128


def normalize_mobile(value):
    if not isinstance(value, str):
        return None
    translated = value.translate(str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789"))
    compact = re.sub(r"[\s()-]", "", translated)
    if not re.fullmatch(r"\+?\d{8,15}", compact):
        return None
    return compact


init_db()


@app.route("/")
def index():
    return render_template("index.html", areas=AREAS)


@app.route("/api/latest-customer-id")
def latest_customer_id():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute(
            "SELECT customer_id FROM job_logs "
            "WHERE customer_id IS NOT NULL AND customer_id != '' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return jsonify({"customer_id": row[0] if row else ""})


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None

    if request.method == "POST":
        submitted_username = request.form.get("username", "").strip()
        submitted_password = request.form.get("password", "")
        with closing(sqlite3.connect(DB_NAME)) as conn:
            account = conn.execute(
                """
                SELECT id, password_hash
                FROM admin_accounts
                WHERE username = ? COLLATE NOCASE OR mobile = ?
                LIMIT 1
                """,
                (
                    normalize_mobile(submitted_username) or submitted_username,
                    normalize_mobile(submitted_username) or submitted_username,
                ),
            ).fetchone()
        if account and check_password_hash(account[1], submitted_password):
            session.clear()
            session["admin_account_id"] = account[0]
            session["admin_csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("admin"))
        error = (
            "No admin account is configured. Set ADMIN_USERNAME and ADMIN_PASSWORD "
            "before starting the app."
            if account is None
            else "Incorrect username or password."
        )

    return render_template("admin_login.html", error=error)


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    if session.get("admin_account_id") is not None:
        verify_admin_csrf_token()
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
def admin():
    account = get_current_admin()
    if account is None:
        return redirect(url_for("admin_login"))

    if "admin_csrf_token" not in session:
        session["admin_csrf_token"] = secrets.token_urlsafe(32)
    csrf_token = session["admin_csrf_token"]
    with closing(sqlite3.connect(DB_NAME)) as conn:
        rows = conn.execute(
            """
            SELECT id, timestamp, work_type, latitude, longitude, accuracy,
                   start_meter, end_meter, total_fiber, onu_id, customer_name,
                   splitter_info, notes, customer_id, tj_details, location,
                   device_info, status, completed_by, completed_at, area
            FROM job_logs
            ORDER BY
                CASE WHEN status = 'done' THEN 1 ELSE 0 END,
                CASE WHEN status = 'done' THEN completed_at END DESC,
                id DESC
            """
        ).fetchall()
    records = [
        {
            "id": row[0],
            "timestamp": row[1],
            "work_type": row[2],
            "latitude": row[3],
            "longitude": row[4],
            "accuracy": row[5],
            "start_meter": row[6],
            "end_meter": row[7],
            "fiber": row[8],
            "onu_id": row[9],
            "customer_name": row[10],
            "splitter": row[11],
            "notes": row[12],
            "customer_id": row[13],
            "pairs": json.loads(row[14] or "[]"),
            "location": row[15],
            "device_info": row[16],
            "status": row[17] or "pending",
            "completed_by": row[18] or "",
            "completed_at": row[19] or "",
            "area": row[20] or "",
        }
        for row in rows
    ]
    team_user_records = [record for record in records if record["work_type"] != "TJ Box"]
    tj_box_records = [record for record in records if record["work_type"] == "TJ Box"]
    return render_template(
        "admin.html",
        team_user_records=team_user_records,
        tj_box_records=tj_box_records,
        csrf_token=csrf_token,
        areas=AREAS,
        account=account,
    )


def verify_admin_csrf_token():
    submitted_token = request.form.get("csrf_token", "")
    expected_token = session.get("admin_csrf_token", "")
    if not expected_token or not hmac.compare_digest(submitted_token, expected_token):
        abort(400, description="Request could not be verified. Refresh the page and try again.")


@app.route("/admin/editors", methods=["POST"])
def admin_add_editor():
    account = get_current_admin()
    if account is None:
        return redirect(url_for("admin_login"))
    if account["role"] != "main":
        abort(403)
    verify_admin_csrf_token()

    editor_name = request.form.get("name", "").strip()
    mobile = normalize_mobile(request.form.get("mobile", "").strip())
    password = request.form.get("password", "")
    if not editor_name or len(editor_name) > 80:
        flash("Enter an editor name up to 80 characters.", "error")
        return redirect(url_for("admin_accounts"))
    if mobile is None:
        flash("Enter a valid mobile number with 8-15 digits.", "error")
        return redirect(url_for("admin_accounts"))
    if not valid_account_password(password):
        flash("Password must be between 8 and 128 characters.", "error")
        return redirect(url_for("admin_accounts"))

    try:
        with closing(sqlite3.connect(DB_NAME)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO admin_accounts
                        (username, password_hash, role, display_name, mobile)
                    VALUES (?, ?, 'editor', ?, ?)
                    """,
                    (mobile, generate_password_hash(password), editor_name, mobile),
                )
    except sqlite3.IntegrityError:
        flash("An account already uses that mobile number.", "error")
        return redirect(url_for("admin_accounts"))

    flash(f"Editor '{editor_name}' added.", "success")
    return redirect(url_for("admin_accounts"))


@app.route("/admin/accounts")
def admin_accounts():
    account = get_current_admin()
    if account is None:
        return redirect(url_for("admin_login"))
    if account["role"] != "main":
        abort(403)
    if "admin_csrf_token" not in session:
        session["admin_csrf_token"] = secrets.token_urlsafe(32)

    with closing(sqlite3.connect(DB_NAME)) as conn:
        editor_accounts = [
            {"name": row[0], "mobile": row[1], "username": row[2]}
            for row in conn.execute(
                "SELECT display_name, mobile, username FROM admin_accounts "
                "WHERE role = 'editor' ORDER BY display_name COLLATE NOCASE, id"
            ).fetchall()
        ]
    return render_template(
        "admin_accounts.html",
        account=account,
        editor_accounts=editor_accounts,
        csrf_token=session["admin_csrf_token"],
    )


@app.route("/admin/password", methods=["POST"])
def admin_change_password():
    account = get_current_admin()
    if account is None:
        return redirect(url_for("admin_login"))
    if account["role"] != "main":
        abort(403)
    verify_admin_csrf_token()

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    with closing(sqlite3.connect(DB_NAME)) as conn:
        row = conn.execute(
            "SELECT password_hash FROM admin_accounts WHERE id = ? AND role = 'main'",
            (account["id"],),
        ).fetchone()
        if row is None or not check_password_hash(row[0], current_password):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("admin_accounts"))

        if not valid_account_password(new_password):
            flash("New password must be between 8 and 128 characters.", "error")
            return redirect(url_for("admin_accounts"))
        if new_password != confirm_password:
            flash("New password and confirmation do not match.", "error")
            return redirect(url_for("admin_accounts"))
        if check_password_hash(row[0], new_password):
            flash("Choose a password different from the current one.", "error")
            return redirect(url_for("admin_accounts"))

        with conn:
            conn.execute(
                "UPDATE admin_accounts SET password_hash = ? "
                "WHERE id = ? AND role = 'main'",
                (generate_password_hash(new_password), account["id"]),
            )

    session.clear()
    flash("Main admin password updated. Please log in with the new password.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin/<int:record_id>/update", methods=["POST"])
def admin_update(record_id):
    if get_current_admin() is None:
        return redirect(url_for("admin_login"))
    verify_admin_csrf_token()

    work_type = request.form.get("work_type", "")
    if work_type not in {"Customer", "TJ Box"}:
        flash("Invalid work type.", "error")
        return redirect(url_for("admin"))
    area = request.form.get("area", "")
    if area and area not in AREAS:
        flash("Invalid area.", "error")
        return redirect(url_for("admin"))

    try:
        latitude_text = request.form.get("latitude", "").strip()
        longitude_text = request.form.get("longitude", "").strip()
        if bool(latitude_text) != bool(longitude_text):
            raise ValueError
        latitude = float(latitude_text) if latitude_text else None
        longitude = float(longitude_text) if longitude_text else None
        accuracy = float(request.form.get("accuracy") or 0)
        start_meter = float(request.form.get("start_meter") or 0)
        end_meter = float(request.form.get("end_meter") or 0)
        if (
            (latitude is not None and not -90 <= latitude <= 90)
            or (longitude is not None and not -180 <= longitude <= 180)
            or not all(
                math.isfinite(value)
                for value in (accuracy, start_meter, end_meter)
            )
            or accuracy < 0
            or (
                latitude is not None
                and not math.isfinite(latitude)
            )
            or (
                longitude is not None
                and not math.isfinite(longitude)
            )
        ):
            raise ValueError
        tj_details = json.loads(request.form.get("tj_details", "[]"))
        if not isinstance(tj_details, list) or any(
            not isinstance(pair, dict) for pair in tj_details
        ):
            raise ValueError
    except (TypeError, ValueError, json.JSONDecodeError):
        flash("Coordinates, meter readings, or pair details are invalid.", "error")
        return redirect(url_for("admin"))

    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cursor = conn.execute(
                """
                UPDATE job_logs
                SET work_type = ?, latitude = ?, longitude = ?, accuracy = ?,
                    start_meter = ?, end_meter = ?, total_fiber = ?, onu_id = ?,
                    customer_name = ?, splitter_info = ?, notes = ?,
                    customer_id = ?, tj_details = ?, location = ?, area = ?
                WHERE id = ?
                """,
                (
                    work_type,
                    latitude,
                    longitude,
                    accuracy,
                    start_meter,
                    end_meter,
                    abs(end_meter - start_meter),
                    request.form.get("onu_id", "").strip(),
                    request.form.get("customer_name", "").strip(),
                    request.form.get("splitter_info", "").strip(),
                    request.form.get("notes", "").strip(),
                    request.form.get("customer_id", "").strip(),
                    json.dumps(tj_details, ensure_ascii=False),
                    request.form.get("location", "").strip(),
                    area,
                    record_id,
                ),
            )
            if cursor.rowcount == 0:
                abort(404)

    flash("Task updated.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/<int:record_id>/delete", methods=["POST"])
def admin_delete(record_id):
    if get_current_admin() is None:
        return redirect(url_for("admin_login"))
    verify_admin_csrf_token()

    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cursor = conn.execute("DELETE FROM job_logs WHERE id = ?", (record_id,))
            if cursor.rowcount == 0:
                abort(404)

    flash("Task deleted.", "success")
    return redirect(url_for("admin"))


@app.route("/api/update-status/<int:job_id>", methods=["POST"])
def update_status(job_id):
    account = get_current_admin()
    if account is None:
        return jsonify({"status": "error", "message": "Admin login required."}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Send valid JSON data."}), 400

    expected_token = session.get("admin_csrf_token", "")
    submitted_token = request.headers.get("X-CSRFToken") or data.get("csrf_token", "")
    if not expected_token or not isinstance(submitted_token, str) or not hmac.compare_digest(
        submitted_token, expected_token
    ):
        return jsonify(
            {"status": "error", "message": "Request could not be verified."}
        ), 400

    new_status = data.get("status")
    if not isinstance(new_status, str) or new_status not in {"pending", "done"}:
        return jsonify({"status": "error", "message": "Choose a valid task status."}), 400

    completed_by = account["display_name"] or account["username"]
    if new_status == "done" and not completed_by:
        return jsonify(
            {"status": "error", "message": "The admin username is not configured."}
        ), 400

    completed_at = (
        datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        if new_status == "done"
        else None
    )
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            cursor = conn.execute(
                """
                UPDATE job_logs
                SET status = ?, completed_by = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    new_status,
                    completed_by if new_status == "done" else None,
                    completed_at,
                    job_id,
                ),
            )
            if cursor.rowcount == 0:
                return jsonify(
                    {"status": "error", "message": "Task not found."}
                ), 404

    return jsonify(
        {
            "status": "success",
            "job_id": job_id,
            "status_value": new_status,
            "completed_by": completed_by if new_status == "done" else "",
            "completed_at": completed_at or "",
        }
    )


@app.route("/api/save-log", methods=["POST"])
def save_log():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "সঠিক JSON তথ্য পাঠান।"}), 400

    try:
        lat = float(data["latitude"])
        lng = float(data["longitude"])
        accuracy = float(data.get("accuracy") or 0)
        if not -90 <= lat <= 90 or not -180 <= lng <= 180 or accuracy < 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify(
            {"status": "error", "message": "সঠিক লোকেশন নির্বাচন করুন।"}
        ), 400

    try:
        start_m = float(data.get("start_meter") or 0)
        end_m = float(data.get("end_meter") or 0)
        total_fiber = abs(end_m - start_m)
    except (TypeError, ValueError):
        return jsonify(
            {"status": "error", "message": "মিটার রিডিং সঠিকভাবে দিন।"}
        ), 400

    work_type = data.get("work_type", "Customer")
    customer_id = str(data.get("customer_id") or "").strip()
    splitter_info = str(data.get("splitter_info") or "").strip()
    location = str(data.get("location") or "").strip()
    area = data.get("area")
    if not isinstance(area, str) or area not in AREAS:
        return jsonify(
            {"status": "error", "message": "একটি বৈধ এলাকা বাছাই করুন।"}
        ), 400
    tj_details = data.get("tj_details") or []
    if not isinstance(tj_details, list):
        return jsonify(
            {"status": "error", "message": "জোড়ার তথ্য সঠিক নয়।"}
        ), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO job_logs (
                    timestamp, work_type, latitude, longitude, accuracy,
                    start_meter, end_meter, total_fiber, onu_id,
                    customer_name, splitter_info, notes, customer_id, tj_details,
                    location, device_info, area
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    work_type,
                    lat,
                    lng,
                    accuracy,
                    start_m,
                    end_m,
                    total_fiber,
                    data.get("onu_id", ""),
                    data.get("customer_name", ""),
                    splitter_info,
                    data.get("notes", ""),
                    customer_id,
                    json.dumps(tj_details, ensure_ascii=False),
                    location,
                    request.headers.get("User-Agent", "")[:500],
                    area,
                ),
            )

    return jsonify(
        {
            "status": "success",
            "message": "তথ্য সফলভাবে সংরক্ষিত হয়েছে!",
            "customer_id": customer_id,
        }
    )


if __name__ == "__main__":
    app.run(
        host="172.31.1.2",
        port=5000,
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
