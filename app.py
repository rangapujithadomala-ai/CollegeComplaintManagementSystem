
from flask import (
    Flask, render_template, request, session, redirect, url_for
)
import sqlite3
import re
from pathlib import Path
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = "college_complaint_system_secret_key"

DATABASE = Path(__file__).resolve().parent / "college_complaints.db"


# -------------------- DATABASE --------------------

def get_connection():
    conn = sqlite3.connect(str(DATABASE))
    conn.row_factory = None
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            student_id TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            student_id TEXT,
            category TEXT
        )
    """)

    columns = {
        row[1]
        for row in cursor.execute(
            "PRAGMA table_info(complaints)"
        ).fetchall()
    }

    if "status" not in columns:
        cursor.execute(
            "ALTER TABLE complaints ADD COLUMN status TEXT DEFAULT 'Pending'"
        )

    if "student_id" not in columns:
        cursor.execute(
            "ALTER TABLE complaints ADD COLUMN student_id TEXT"
        )

    if "category" not in columns:
        cursor.execute(
            "ALTER TABLE complaints ADD COLUMN category TEXT"
        )

    conn.commit()
    conn.close()


def get_complaints():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints ORDER BY id DESC")
    complaints = cursor.fetchall()

    conn.close()
    return complaints


# -------------------- PASSWORD VALIDATION --------------------

def password_error(password):
    if len(password) < 8:
        return "Password must be at least 8 characters long!"

    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter!"

    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter!"

    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number!"

    if not re.search(r"[^A-Za-z0-9]", password):
        return "Password must contain at least one special character!"

    return None


# -------------------- LOGIN PROTECTION --------------------

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "student_id" not in session:
            return redirect(url_for("student_login"))
        return view(*args, **kwargs)
    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped_view


@app.context_processor
def inject_student_profile():
    return {
        "student_profile": {
            "name": session.get("student_name", ""),
            "id": session.get("student_roll_id", ""),
            "email": session.get("student_email", "")
        },
        "is_student_logged_in": "student_id" in session,
        "is_admin_logged_in": bool(session.get("is_admin"))
    }


# -------------------- HOME --------------------

@app.route("/")
def home():
    return render_template("index.html")


# -------------------- STUDENT REGISTRATION --------------------

@app.route("/student-register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        roll_id = request.form.get("student_id", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([name, roll_id, email, password, confirm_password]):
            return render_template(
                "error.html",
                message="Please fill in all the required fields."
            ), 400

        if password != confirm_password:
            return render_template(
                "error.html",
                message="Passwords do not match!"
            ), 400

        error = password_error(password)
        if error:
            return render_template("error.html", message=error), 400

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT id FROM students
                WHERE lower(email) = ? OR student_id = ?
            """, (email, roll_id))

            if cursor.fetchone():
                return render_template(
                    "error.html",
                    message="This email or student ID is already registered."
                ), 409

            cursor.execute("""
                INSERT INTO students (name, student_id, email, password)
                VALUES (?, ?, ?, ?)
            """, (
                name,
                roll_id,
                email,
                generate_password_hash(password)
            ))

            conn.commit()

        finally:
            conn.close()

        return render_template(
            "success.html",
            success_type="registration"
        )

    return render_template("student_register.html")


# -------------------- STUDENT LOGIN --------------------

@app.route("/student-login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, student_id, email, password
            FROM students
            WHERE lower(email) = ?
        """, (email,))

        student = cursor.fetchone()

        if student is not None:
            stored_password = student[4]

            # Support old accounts whose passwords were stored as plain text.
            # Upgrade their password hash after a successful login.
            try:
                password_matches = check_password_hash(
                    stored_password, password
                )
            except (ValueError, TypeError):
                password_matches = False

            if not password_matches and stored_password == password:
                password_matches = True
                cursor.execute(
                    "UPDATE students SET password = ? WHERE id = ?",
                    (generate_password_hash(password), student[0])
                )
                conn.commit()
        else:
            password_matches = False

        conn.close()

        if student is None or not password_matches:
            return render_template(
                "error.html",
                message="Invalid email or password. Please try again."
            ), 401

        session.clear()
        session["student_id"] = student[0]
        session["student_name"] = student[1]
        session["student_roll_id"] = student[2]
        session["student_email"] = student[3]

        return redirect(url_for("student_dashboard"))

    return render_template("student_login.html")


@app.route("/student-dashboard")
@login_required
def student_dashboard():
    return render_template("student_dashboard.html")


# -------------------- STUDENT FORGOT PASSWORD --------------------

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        roll_id = request.form.get("student_id", "").strip()

        if not email or not roll_id:
            return render_template(
                "error.html",
                message="Please enter your registered email and student ID."
            ), 400

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id FROM students
            WHERE lower(email) = ? AND student_id = ?
        """, (email, roll_id))

        student = cursor.fetchone()
        conn.close()

        if student is None:
            return render_template(
                "error.html",
                message="The email and student ID do not match our records."
            ), 400

        # Allow password reset only in this browser session.
        session.clear()
        session["password_reset_student_id"] = student[0]

        return redirect(url_for("reset_password"))

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    student_db_id = session.get("password_reset_student_id")

    if not student_db_id:
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not password or not confirm_password:
            return render_template(
                "error.html",
                message="Please enter and confirm your new password."
            ), 400

        if password != confirm_password:
            return render_template(
                "error.html",
                message="Passwords do not match!"
            ), 400

        error = password_error(password)
        if error:
            return render_template("error.html", message=error), 400

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE students
            SET password = ?
            WHERE id = ?
        """, (generate_password_hash(password), student_db_id))

        conn.commit()
        conn.close()

        session.pop("password_reset_student_id", None)

        return render_template(
            "success.html",
            success_type="password_reset"
        )

    return render_template("reset_password.html")


# -------------------- COMPLAINT SUBMISSION --------------------

@app.route("/submit-complaint", methods=["GET", "POST"])
@login_required
def submit_complaint():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()

        if category.lower() == "other":
            category = request.form.get("other_category", "").strip()

        if not title or not description or not category:
            return render_template(
                "error.html",
                message="Please complete all complaint fields."
            ), 400

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO complaints
                (title, description, status, student_id, category)
            VALUES (?, ?, 'Pending', ?, ?)
        """, (
            title,
            description,
            session["student_id"],
            category
        ))

        conn.commit()
        conn.close()

        return render_template(
            "success.html",
            success_type="complaint"
        )

    return render_template("submit_complaint.html")


@app.route("/my-complaints")
@login_required
def my_complaints():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM complaints
        WHERE student_id = ?
        ORDER BY id DESC
    """, (session["student_id"],))

    complaints = cursor.fetchall()
    conn.close()

    return render_template(
        "my_complaints.html",
        complaints=complaints
    )


# -------------------- ADMIN LOGIN --------------------

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == "admin" and password == "admin123":
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))

        return render_template(
            "error.html",
            message="Invalid admin username or password."
        ), 401

    return render_template("admin_login.html")


# -------------------- ADMIN DASHBOARD --------------------

@app.route("/admin-dashboard")
@admin_required
def admin_dashboard():
    return render_template(
        "admin_dashboard.html",
        complaints=get_complaints()
    )


@app.route("/update-status/<int:complaint_id>", methods=["POST"])
@admin_required
def update_status(complaint_id):
    status = request.form.get("status", "").strip()

    allowed_statuses = {
        "Pending",
        "In Progress",
        "Resolved",
        "Rejected"
    }

    if status not in allowed_statuses:
        return "Invalid complaint status.", 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE complaints SET status = ? WHERE id = ?",
        (status, complaint_id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


# -------------------- LOGOUT --------------------

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))


# -------------------- RUN APPLICATION --------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=False, port=5001)
