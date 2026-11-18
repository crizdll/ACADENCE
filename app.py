from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import date
from pathlib import Path

app = Flask(__name__)
app.secret_key = "replace-this-with-a-long-random-secret-before-deployment"
DATABASE = Path(__file__).with_name("acadtrack.db")
PASSING_GRADE = 75


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_db_connection()

    # Keep a copy of an older single-user database before creating the account-based tables.
    old_subjects = connection.execute("PRAGMA table_info(subjects)").fetchall()
    if old_subjects and "user_id" not in [column["name"] for column in old_subjects]:
        connection.execute("ALTER TABLE subjects RENAME TO subjects_legacy")
    old_assignments = connection.execute("PRAGMA table_info(assignments)").fetchall()
    if old_assignments and "user_id" not in [column["name"] for column in old_assignments]:
        connection.execute("ALTER TABLE assignments RENAME TO assignments_legacy")

    connection.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        quiz_count INTEGER NOT NULL DEFAULT 3,
        activity_count INTEGER NOT NULL DEFAULT 3,
        oral_count INTEGER NOT NULL DEFAULT 0,
        project_count INTEGER NOT NULL DEFAULT 0,
        quiz_scores TEXT NOT NULL DEFAULT '',
        quiz_max_scores TEXT NOT NULL DEFAULT '',
        activity_scores TEXT NOT NULL DEFAULT '',
        activity_max_scores TEXT NOT NULL DEFAULT '',
        oral_scores TEXT NOT NULL DEFAULT '',
        oral_max_scores TEXT NOT NULL DEFAULT '',
        project_scores TEXT NOT NULL DEFAULT '',
        project_max_scores TEXT NOT NULL DEFAULT '',
        prelim_score REAL NOT NULL DEFAULT 0,
        prelim_max_score REAL NOT NULL DEFAULT 100,
        midterm_score REAL NOT NULL DEFAULT 0,
        midterm_max_score REAL NOT NULL DEFAULT 100,
        final_score REAL NOT NULL DEFAULT 0,
        final_max_score REAL NOT NULL DEFAULT 100,
        quiz_weight REAL NOT NULL DEFAULT 20,
        activity_weight REAL NOT NULL DEFAULT 20,
        oral_weight REAL NOT NULL DEFAULT 0,
        project_weight REAL NOT NULL DEFAULT 0,
        prelim_weight REAL NOT NULL DEFAULT 20,
        midterm_weight REAL NOT NULL DEFAULT 20,
        final_weight REAL NOT NULL DEFAULT 20,
        UNIQUE(user_id, name),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        subject_id INTEGER,
        due_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        description TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(subject_id) REFERENCES subjects(id)
    )""")
    # Add maximum-score columns when opening a database created by an older version.
    existing_columns = [column["name"] for column in connection.execute("PRAGMA table_info(subjects)").fetchall()]
    new_columns = {
        "quiz_max_scores": "TEXT NOT NULL DEFAULT ''",
        "activity_max_scores": "TEXT NOT NULL DEFAULT ''",
        "prelim_max_score": "REAL NOT NULL DEFAULT 100",
        "midterm_max_score": "REAL NOT NULL DEFAULT 100",
        "final_max_score": "REAL NOT NULL DEFAULT 100",
        "oral_count": "INTEGER NOT NULL DEFAULT 0",
        "project_count": "INTEGER NOT NULL DEFAULT 0",
        "oral_scores": "TEXT NOT NULL DEFAULT ''",
        "oral_max_scores": "TEXT NOT NULL DEFAULT ''",
        "project_scores": "TEXT NOT NULL DEFAULT ''",
        "project_max_scores": "TEXT NOT NULL DEFAULT ''",
        "oral_weight": "REAL NOT NULL DEFAULT 0",
        "project_weight": "REAL NOT NULL DEFAULT 0",
    }
    for column_name, column_type in new_columns.items():
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE subjects ADD COLUMN {column_name} {column_type}")

    # Preserve grades entered in an older version by treating their old scores as out of 100.
    old_subject_rows = connection.execute("SELECT id, quiz_count, activity_count, quiz_max_scores, activity_max_scores FROM subjects").fetchall()
    for old_subject in old_subject_rows:
        if not old_subject["quiz_max_scores"] and old_subject["quiz_count"]:
            quiz_defaults = ",".join(["100"] * old_subject["quiz_count"])
            connection.execute("UPDATE subjects SET quiz_max_scores = ? WHERE id = ?", (quiz_defaults, old_subject["id"]))
        if not old_subject["activity_max_scores"] and old_subject["activity_count"]:
            activity_defaults = ",".join(["100"] * old_subject["activity_count"])
            connection.execute("UPDATE subjects SET activity_max_scores = ? WHERE id = ?", (activity_defaults, old_subject["id"]))
    connection.commit()
    connection.close()


def login_required():
    return "user_id" in session


def parse_scores(value):
    """Read a comma-separated list of numbers. Empty entries are skipped."""
    if not value or not value.strip():
        return []
    return [float(score.strip()) for score in value.split(",") if score.strip()]


def parse_score_slots(value, count):
    """Read partial score lists; missing positions mean assessments not graded yet."""
    slots = []
    if value and value.strip():
        for part in value.split(","):
            cleaned = part.strip()
            slots.append(float(cleaned) if cleaned and cleaned != "-" else None)
    # Never fail just because a student has entered only some of the assessments.
    if len(slots) < count:
        slots.extend([None] * (count - len(slots)))
    return slots[:count]


def calculate_grade_details(subject):
    """Calculate an in-progress estimate from the assessment categories used by a subject."""
    category_results = []
    assessment_groups = [
        ("quiz", "quiz_count", "quiz_scores", "quiz_max_scores", "quiz_weight"),
        ("activity", "activity_count", "activity_scores", "activity_max_scores", "activity_weight"),
        ("oral presentation", "oral_count", "oral_scores", "oral_max_scores", "oral_weight"),
        ("project", "project_count", "project_scores", "project_max_scores", "project_weight"),
    ]
    for _, count_key, score_key, max_key, weight_key in assessment_groups:
        count = subject[count_key]
        weight = subject[weight_key]
        scores = parse_score_slots(subject[score_key], count)
        maximum_slots = parse_score_slots(subject[max_key], count)
        maximums = [maximum if maximum is not None else 100.0 for maximum in maximum_slots]
        completed = [(score, maximum) for score, maximum in zip(scores, maximums)
                     if score is not None and maximum > 0]
        if completed and weight > 0:
            earned = sum(pair[0] for pair in completed)
            possible = sum(pair[1] for pair in completed)
            category_results.append((earned / possible * 100, weight))

    exams = [
        (subject["prelim_score"], subject["prelim_max_score"], subject["prelim_weight"]),
        (subject["midterm_score"], subject["midterm_max_score"], subject["midterm_weight"]),
        (subject["final_score"], subject["final_max_score"], subject["final_weight"]),
    ]
    for earned, maximum, weight in exams:
        if earned is not None and earned >= 0 and maximum > 0 and weight > 0:
            category_results.append((earned / maximum * 100, weight))

    if not category_results:
        return {"grade": 0.0, "has_scores": False, "completed_categories": 0}
    used_weight = sum(weight for _, weight in category_results)
    estimate = sum(percent * weight for percent, weight in category_results) / used_weight
    return {"grade": estimate, "has_scores": True, "completed_categories": len(category_results)}


def calculate_grade(subject):
    return calculate_grade_details(subject)["grade"]


def assessment_percent(earned, maximum):
    return (earned / maximum * 100) if maximum > 0 else 0


def get_deadline_status(due_date, task_status):
    if task_status == "Completed":
        return "Completed", "green"
    days_left = (date.fromisoformat(due_date) - date.today()).days
    if days_left < 0:
        return "Overdue", "red"
    if days_left <= 1:
        return "Due soon", "red"
    if days_left <= 2:
        return "Approaching", "yellow"
    return "Upcoming", "green"


@app.route("/register", methods=["GET", "POST"])
def register():
    form_data = {}
    if request.method == "POST":
        form_data = {"username": request.form.get("username", "")}
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(username) < 3 or len(password) < 8:
            flash("Use a username with at least 3 characters and a password with at least 8 characters.", "error")
        elif password != confirm:
            flash("The passwords do not match.", "error")
        else:
            connection = get_db_connection()
            try:
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password))
                )
                connection.commit()
                session["user_id"] = cursor.lastrowid
                session["username"] = username
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("That username is already taken. Please choose another.", "error")
            finally:
                connection.close()
    return render_template("auth.html", mode="register", form_data=form_data)


@app.route("/login", methods=["GET", "POST"])
def login():
    form_data = {}
    if request.method == "POST":
        form_data = {"username": request.form.get("username", "")}
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        connection = get_db_connection()
        user = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        connection.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("auth.html", mode="login", form_data=form_data)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.before_request
def require_login():
    allowed = {"login", "register", "static"}
    if request.endpoint not in allowed and not login_required():
        return redirect(url_for("login"))


@app.route("/")
def dashboard():
    connection = get_db_connection()
    user_id = session["user_id"]
    subjects = connection.execute("SELECT * FROM subjects WHERE user_id = ? ORDER BY name", (user_id,)).fetchall()
    assignments = connection.execute("""SELECT assignments.*, subjects.name AS subject_name
        FROM assignments LEFT JOIN subjects ON assignments.subject_id = subjects.id
        WHERE assignments.user_id = ? ORDER BY assignments.due_date""", (user_id,)).fetchall()
    connection.close()
    subject_cards = []
    for subject in subjects:
        details = calculate_grade_details(subject)
        grade = details["grade"]
        subject_cards.append({"name": subject["name"], "grade": grade, "has_scores": details["has_scores"],
                              "standing": ("At Risk" if grade < PASSING_GRADE else "Passing") if details["has_scores"] else "No scores yet",
                              "color": ("red" if grade < PASSING_GRADE else "green") if details["has_scores"] else "blue"})
    task_cards = []
    for task in assignments:
        label, color = get_deadline_status(task["due_date"], task["status"])
        task_cards.append({"id": task["id"], "title": task["title"],
                           "subject_name": task["subject_name"] or "No subject",
                           "due_date": task["due_date"], "status": task["status"],
                           "deadline_label": label, "color": color})
    return render_template("dashboard.html", subjects=subject_cards, assignments=task_cards[:5],
        pending_count=sum(1 for task in task_cards if task["status"] != "Completed"),
        completed_count=sum(1 for task in task_cards if task["status"] == "Completed"),
        warning_count=sum(1 for subject in subject_cards if subject["standing"] == "At Risk"))


@app.route("/assignments", methods=["GET", "POST"])
def assignments():
    connection = get_db_connection()
    user_id = session["user_id"]
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subject_id = request.form.get("subject_id") or None
        due_date = request.form.get("due_date", "")
        description = request.form.get("description", "").strip()
        try:
            date.fromisoformat(due_date)
            if not title:
                raise ValueError
            if subject_id:
                valid_subject = connection.execute("SELECT id FROM subjects WHERE id = ? AND user_id = ?", (subject_id, user_id)).fetchone()
                if not valid_subject:
                    raise ValueError
            connection.execute("INSERT INTO assignments (user_id, title, subject_id, due_date, description) VALUES (?, ?, ?, ?, ?)",
                               (user_id, title, subject_id, due_date, description))
            connection.commit()
            flash("Assignment added successfully.", "success")
        except (ValueError, TypeError):
            flash("Please check the assignment title, selected subject, and due date. Your entries have been kept so you can correct them.", "error")
            form_data = request.form.to_dict()
            connection.close()
            connection = get_db_connection()
            tasks = connection.execute("""SELECT assignments.*, subjects.name AS subject_name FROM assignments
                LEFT JOIN subjects ON assignments.subject_id = subjects.id WHERE assignments.user_id = ?
                ORDER BY assignments.due_date""", (user_id,)).fetchall()
            subject_list = connection.execute("SELECT * FROM subjects WHERE user_id = ? ORDER BY name", (user_id,)).fetchall()
            connection.close()
            task_cards = []
            for task in tasks:
                label, color = get_deadline_status(task["due_date"], task["status"])
                task_cards.append({"id": task["id"], "title": task["title"], "subject_name": task["subject_name"] or "No subject",
                    "due_date": task["due_date"], "status": task["status"], "description": task["description"],
                    "deadline_label": label, "color": color})
            return render_template("assignments.html", assignments=task_cards, subjects=subject_list, form_data=form_data)
        connection.close()
        return redirect(url_for("assignments"))
    form_data = {}
    tasks = connection.execute("""SELECT assignments.*, subjects.name AS subject_name FROM assignments
        LEFT JOIN subjects ON assignments.subject_id = subjects.id WHERE assignments.user_id = ?
        ORDER BY assignments.due_date""", (user_id,)).fetchall()
    subject_list = connection.execute("SELECT * FROM subjects WHERE user_id = ? ORDER BY name", (user_id,)).fetchall()
    connection.close()
    task_cards = []
    for task in tasks:
        label, color = get_deadline_status(task["due_date"], task["status"])
        task_cards.append({"id": task["id"], "title": task["title"], "subject_name": task["subject_name"] or "No subject",
            "due_date": task["due_date"], "status": task["status"], "description": task["description"],
            "deadline_label": label, "color": color})
    return render_template("assignments.html", assignments=task_cards, subjects=subject_list, form_data=form_data)


@app.route("/assignment/<int:assignment_id>/complete", methods=["POST"])
def complete_assignment(assignment_id):
    connection = get_db_connection()
    connection.execute("UPDATE assignments SET status = 'Completed' WHERE id = ? AND user_id = ?", (assignment_id, session["user_id"]))
    connection.commit(); connection.close()
    flash("Assignment marked as completed.", "success")
    return redirect(url_for("assignments"))


@app.route("/assignment/<int:assignment_id>/delete", methods=["POST"])
def delete_assignment(assignment_id):
    connection = get_db_connection()
    connection.execute("DELETE FROM assignments WHERE id = ? AND user_id = ?", (assignment_id, session["user_id"]))
    connection.commit(); connection.close()
    flash("Assignment deleted.", "success")
    return redirect(url_for("assignments"))


def save_subject(form, user_id):
    name = form.get("name", "").strip()
    groups = ["quiz", "activity", "oral", "project"]
    counts, scores_by_group, maximums_by_group = {}, {}, {}
    for group in groups:
        requested_count = int(form.get(f"{group}_count", 0) or 0)
        entered_scores = form.get(f"{group}_scores", "")
        entered_maximums = form.get(f"{group}_max_scores", "")
        # The count control is authoritative, so setting it to 0 cleanly removes
        # an assessment type even if old score text is still present in the form.
        count = requested_count
        if count < 0 or count > 50:
            raise ValueError("Each assessment type can have up to 50 entries.")
        counts[group] = count
        scores_by_group[group] = parse_score_slots(entered_scores, count)
        maximum_slots = parse_score_slots(entered_maximums, count)
        # A missing maximum defaults to 100 points; blank score slots stay ungraded.
        maximums_by_group[group] = [maximum if maximum is not None else 100.0 for maximum in maximum_slots]

    prelim_text = form.get("prelim_score", "").strip()
    midterm_text = form.get("midterm_score", "").strip()
    final_text = form.get("final_score", "").strip()
    prelim = float(prelim_text) if prelim_text else -1
    midterm = float(midterm_text) if midterm_text else -1
    final = float(final_text) if final_text else -1
    prelim_max = float(form.get("prelim_max_score", 100) or 100)
    midterm_max = float(form.get("midterm_max_score", 100) or 100)
    final_max = float(form.get("final_max_score", 100) or 100)
    weight_keys = ["quiz_weight", "activity_weight", "oral_weight", "project_weight", "prelim_weight", "midterm_weight", "final_weight"]
    weights = [float(form.get(key, 0) or 0) for key in weight_keys]

    if not name:
        raise ValueError("Please enter a subject name.")
    for group in groups:
        if any(maximum <= 0 for maximum in maximums_by_group[group]):
            raise ValueError("Every maximum score must be greater than zero.")
    all_scores = []
    all_maximums = []
    for group in groups:
        all_scores.extend(scores_by_group[group])
        all_maximums.extend(maximums_by_group[group])
    all_scores.extend([prelim, midterm, final])
    all_maximums.extend([prelim_max, midterm_max, final_max])
    if any(maximum <= 0 for maximum in all_maximums):
        raise ValueError("Every maximum score must be greater than zero.")
    # -1 is the database sentinel for an exam that has not been taken yet.
    if any(score is not None and score < 0 and score != -1 for score in all_scores):
        raise ValueError("Scores cannot be negative.")
    pairs = [(score, maximum) for score, maximum in zip(all_scores, all_maximums) if score is not None and score >= 0]
    if any(score > maximum for score, maximum in pairs):
        raise ValueError("A score earned cannot be greater than its maximum possible points.")
    if any(weight < 0 or weight > 100 for weight in weights):
        raise ValueError("Each grading percentage must be between 0 and 100%.")
    if abs(sum(weights) - 100) > 0.01:
        raise ValueError("All grading percentages, including optional assessment categories, must add up to 100%.")

    connection = get_db_connection()
    connection.execute("""INSERT INTO subjects (
        user_id, name, quiz_count, activity_count, oral_count, project_count,
        quiz_scores, quiz_max_scores, activity_scores, activity_max_scores,
        oral_scores, oral_max_scores, project_scores, project_max_scores,
        prelim_score, prelim_max_score, midterm_score, midterm_max_score, final_score, final_max_score,
        quiz_weight, activity_weight, oral_weight, project_weight, prelim_weight, midterm_weight, final_weight)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, name) DO UPDATE SET
        quiz_count=excluded.quiz_count, activity_count=excluded.activity_count,
        oral_count=excluded.oral_count, project_count=excluded.project_count,
        quiz_scores=excluded.quiz_scores, quiz_max_scores=excluded.quiz_max_scores,
        activity_scores=excluded.activity_scores, activity_max_scores=excluded.activity_max_scores,
        oral_scores=excluded.oral_scores, oral_max_scores=excluded.oral_max_scores,
        project_scores=excluded.project_scores, project_max_scores=excluded.project_max_scores,
        prelim_score=excluded.prelim_score, prelim_max_score=excluded.prelim_max_score,
        midterm_score=excluded.midterm_score, midterm_max_score=excluded.midterm_max_score,
        final_score=excluded.final_score, final_max_score=excluded.final_max_score,
        quiz_weight=excluded.quiz_weight, activity_weight=excluded.activity_weight,
        oral_weight=excluded.oral_weight, project_weight=excluded.project_weight,
        prelim_weight=excluded.prelim_weight, midterm_weight=excluded.midterm_weight, final_weight=excluded.final_weight""",
        (user_id, name, counts["quiz"], counts["activity"], counts["oral"], counts["project"],
         ",".join("" if score is None else str(score) for score in scores_by_group["quiz"]), ",".join(map(str, maximums_by_group["quiz"])),
         ",".join("" if score is None else str(score) for score in scores_by_group["activity"]), ",".join(map(str, maximums_by_group["activity"])),
         ",".join("" if score is None else str(score) for score in scores_by_group["oral"]), ",".join(map(str, maximums_by_group["oral"])),
         ",".join("" if score is None else str(score) for score in scores_by_group["project"]), ",".join(map(str, maximums_by_group["project"])),
         prelim, prelim_max, midterm, midterm_max, final, final_max, *weights))
    connection.commit()
    connection.close()


@app.route("/grades", methods=["GET", "POST"])
def grades():
    form_data = {}
    if request.method == "POST":
        try:
            save_subject(request.form, session["user_id"])
            flash("Subject grades saved successfully.", "success")
            return redirect(url_for("grades"))
        except (ValueError, TypeError) as error:
            flash((str(error) or "Please enter valid numbers.") + " Your entries have been kept so you can correct them.", "error")
            form_data = request.form.to_dict()
    connection = get_db_connection()
    subjects = connection.execute("SELECT * FROM subjects WHERE user_id = ? ORDER BY name", (session["user_id"],)).fetchall()
    connection.close()
    cards = []
    for subject in subjects:
        item = dict(subject)
        grade_details = calculate_grade_details(subject)
        item["grade"] = grade_details["grade"]
        item["has_scores"] = grade_details["has_scores"]
        item["completed_categories"] = grade_details["completed_categories"]
        item["standing"] = "At Risk" if item["grade"] < PASSING_GRADE else "Passing"
        item["quiz_score_slots"] = parse_score_slots(subject["quiz_scores"], subject["quiz_count"])
        item["quiz_max_score_list"] = [value if value is not None else 100.0 for value in parse_score_slots(subject["quiz_max_scores"], subject["quiz_count"])]
        item["activity_score_slots"] = parse_score_slots(subject["activity_scores"], subject["activity_count"])
        item["activity_max_score_list"] = [value if value is not None else 100.0 for value in parse_score_slots(subject["activity_max_scores"], subject["activity_count"])]
        item["oral_score_slots"] = parse_score_slots(subject["oral_scores"], subject["oral_count"])
        item["oral_max_score_list"] = [value if value is not None else 100.0 for value in parse_score_slots(subject["oral_max_scores"], subject["oral_count"])]
        item["project_score_slots"] = parse_score_slots(subject["project_scores"], subject["project_count"])
        item["project_max_score_list"] = [value if value is not None else 100.0 for value in parse_score_slots(subject["project_max_scores"], subject["project_count"])]
        cards.append(item)
    return render_template("grades.html", subjects=cards, form_data=form_data)


@app.route("/subject/<int:subject_id>/delete", methods=["POST"])
def delete_subject(subject_id):
    connection = get_db_connection()
    connection.execute("UPDATE assignments SET subject_id = NULL WHERE subject_id = ? AND user_id = ?", (subject_id, session["user_id"]))
    connection.execute("DELETE FROM subjects WHERE id = ? AND user_id = ?", (subject_id, session["user_id"]))
    connection.commit(); connection.close()
    flash("Subject deleted. Its assignments were kept.", "success")
    return redirect(url_for("grades"))


@app.route("/planner")
def planner():
    connection = get_db_connection()
    user_id = session["user_id"]
    subjects = connection.execute("SELECT * FROM subjects WHERE user_id = ? ORDER BY name", (user_id,)).fetchall()
    tasks = connection.execute("""SELECT assignments.*, subjects.name AS subject_name FROM assignments
        LEFT JOIN subjects ON assignments.subject_id = subjects.id WHERE assignments.user_id = ?
        AND assignments.status != 'Completed' ORDER BY assignments.due_date""", (user_id,)).fetchall()
    connection.close()
    priorities = []
    for subject in subjects:
        details = calculate_grade_details(subject)
        grade = details["grade"]
        if details["has_scores"] and grade < PASSING_GRADE:
            priorities.append({"title": subject["name"], "reason": f"Current estimated grade is {grade:.2f}%, below the passing mark of {PASSING_GRADE}%.", "level": "High", "sort": 0})
    for task in tasks:
        label, color = get_deadline_status(task["due_date"], task["status"])
        level, sort = ("High", 0) if label in ["Overdue", "Due soon"] else (("Medium", 1) if label == "Approaching" else ("Low", 2))
        priorities.append({"title": task["title"], "reason": f"{task['subject_name'] or 'No subject'} · Due {task['due_date']} · {label}", "level": level, "sort": sort})
    priorities.sort(key=lambda item: item["sort"])
    return render_template("planner.html", priorities=priorities)


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
