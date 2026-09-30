from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import date, timedelta

app = Flask(__name__)
app.secret_key = "greenhabit_secret_key"


# ---------------- DATABASE ----------------

def create_database():

    conn = sqlite3.connect("greenhabit.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            habit_id INTEGER,
            UNIQUE(user_id, habit_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            habit_id INTEGER,
            log_date TEXT,
            completed INTEGER DEFAULT 0,
            UNIQUE(user_id, habit_id, log_date)
        )
    """)

    habits = [
        ("Save Water", "Water"),
        ("Save Electricity", "Energy"),
        ("Recycle Waste", "Waste"),
        ("Avoid Plastic", "Environment"),
        ("Use Public Transport", "Transport"),
        ("Care for Plants", "Nature")
    ]

    for habit in habits:
        cursor.execute(
            "INSERT OR IGNORE INTO habits (name, category) VALUES (?, ?)",
            habit
        )

    conn.commit()
    conn.close()


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("greenhabit.db")
        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO users (name, email, password)
                VALUES (?, ?, ?)
                """,
                (name, email, password)
            )

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:

            conn.close()

            return "This email is already registered."

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("greenhabit.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, name
            FROM users
            WHERE email = ? AND password = ?
            """,
            (email, password)
        )

        user = cursor.fetchone()

        conn.close()

        if user:

            session["user_id"] = user[0]
            session["user_name"] = user[1]

            return redirect("/dashboard")

        else:

            return "Invalid email or password."

    return render_template("login.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = sqlite3.connect("greenhabit.db")
    cursor = conn.cursor()

    # Total selected habits
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM user_habits
        WHERE user_id = ?
        """,
        (user_id,)
    )

    total_habits = cursor.fetchone()[0]

    # Today's completed habits
    today = str(date.today())

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM habit_logs
        WHERE user_id = ?
        AND log_date = ?
        AND completed = 1
        """,
        (user_id, today)
    )

    completed_today = cursor.fetchone()[0]

    conn.close()

    # Calculate percentage
    if total_habits > 0:
        progress = int((completed_today / total_habits) * 100)
    else:
        progress = 0

    # Calculate streak
    streak = calculate_streak(user_id)

    return render_template(
        "dashboard.html",
        name=session["user_name"],
        total_habits=total_habits,
        completed_today=completed_today,
        progress=progress,
        streak=streak
    )


# ---------------- STREAK ----------------

def calculate_streak(user_id):

    conn = sqlite3.connect("greenhabit.db")
    cursor = conn.cursor()

    streak = 0

    current_date = date.today()

    while True:

        day = str(current_date)

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM habit_logs
            WHERE user_id = ?
            AND log_date = ?
            AND completed = 1
            """,
            (user_id, day)
        )

        completed = cursor.fetchone()[0]

        if completed > 0:

            streak += 1

            current_date = current_date - timedelta(days=1)

        else:

            break

    conn.close()

    return streak


# ---------------- SELECT HABITS ----------------

@app.route("/habits", methods=["GET", "POST"])
def habits():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = sqlite3.connect("greenhabit.db")
    cursor = conn.cursor()

    if request.method == "POST":

        selected_habits = request.form.getlist("habits")

        cursor.execute(
            """
            DELETE FROM user_habits
            WHERE user_id = ?
            """,
            (user_id,)
        )

        for habit_id in selected_habits:

            cursor.execute(
                """
                INSERT INTO user_habits
                (user_id, habit_id)
                VALUES (?, ?)
                """,
                (user_id, habit_id)
            )

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    cursor.execute(
        """
        SELECT id, name, category
        FROM habits
        """
    )

    all_habits = cursor.fetchall()

    cursor.execute(
        """
        SELECT habit_id
        FROM user_habits
        WHERE user_id = ?
        """,
        (user_id,)
    )

    selected = [row[0] for row in cursor.fetchall()]

    conn.close()

    return render_template(
        "habits.html",
        habits=all_habits,
        selected=selected
    )


# ---------------- TRACK HABITS ----------------

@app.route("/track", methods=["GET", "POST"])
def track():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    today = str(date.today())

    conn = sqlite3.connect("greenhabit.db")
    cursor = conn.cursor()

    if request.method == "POST":

        completed_habits = request.form.getlist("completed")

        cursor.execute(
            """
            SELECT habit_id
            FROM user_habits
            WHERE user_id = ?
            """,
            (user_id,)
        )

        selected_habits = [row[0] for row in cursor.fetchall()]

        for habit_id in selected_habits:

            if str(habit_id) in completed_habits:
                completed = 1
            else:
                completed = 0

            cursor.execute(
                """
                INSERT INTO habit_logs
                (user_id, habit_id, log_date, completed)
                VALUES (?, ?, ?, ?)

                ON CONFLICT(user_id, habit_id, log_date)
                DO UPDATE SET completed = excluded.completed
                """,
                (user_id, habit_id, today, completed)
            )

        conn.commit()

    cursor.execute(
        """
        SELECT habits.id, habits.name, habits.category
        FROM habits
        INNER JOIN user_habits
        ON habits.id = user_habits.habit_id
        WHERE user_habits.user_id = ?
        """,
        (user_id,)
    )

    user_habits = cursor.fetchall()

    cursor.execute(
        """
        SELECT habit_id
        FROM habit_logs
        WHERE user_id = ?
        AND log_date = ?
        AND completed = 1
        """,
        (user_id, today)
    )

    completed_today = [row[0] for row in cursor.fetchall()]

    conn.close()

    return render_template(
        "track.html",
        habits=user_habits,
        completed=completed_today,
        today=today
    )

#-----------------WEEKLY PROGRESS---------

@app.route("/progress")
def progress():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    conn = sqlite3.connect("greenhabit.db")
    cursor = conn.cursor()

    weekly_data = []

    today = date.today()

    for i in range(6,-1,-1):
        current_date = today -timedelta(days=i)

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM habit_logs
            WHERE user_id = ?
            AND log_date = ?
            AND completed = 1
            """,
            (user_id,str(current_date))
        )

        completed = cursor.fetchone()[0]
        weekly_data.append({
            "date":str(current_date),
            "completed":completed
        })

        conn.close()

        return render_template(
            "progress.html",
            weekly_data=weekly_data
        )
# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ---------------- START APP ----------------

if __name__ == "__main__":

    create_database()

    app.run(debug=True)