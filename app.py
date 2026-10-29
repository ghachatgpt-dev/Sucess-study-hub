import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "student_success.db"

st.set_page_config(page_title="Student Success Hub", page_icon="🎓", layout="wide")

# ---------- Database ----------
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT DEFAULT '',
            due_date TEXT,
            priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Pending',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            subject TEXT NOT NULL,
            location TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            assessment TEXT DEFAULT '',
            score REAL NOT NULL,
            max_score REAL NOT NULL,
            assessment_date TEXT
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT DEFAULT '',
            content TEXT DEFAULT '',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            target_date TEXT,
            completed INTEGER DEFAULT 0
        );
        """)

init_db()

def query_df(sql, params=()):
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)

def execute(sql, params=()):
    with get_connection() as conn:
        conn.execute(sql, params)
        conn.commit()

def safe_date(value):
    try:
        return date.fromisoformat(value).strftime("%d %b %Y")
    except (ValueError, TypeError):
        return "Not set"

# ---------- Sidebar ----------
st.sidebar.title("🎓 Student Success Hub")
st.sidebar.caption("Your study life, organised.")
page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Tasks & Assignments", "Study Timetable", "Grades & Progress", "Notes", "Goals", "About"]
)
st.sidebar.divider()
st.sidebar.info("Tip: Add your real tasks, classes, and scores to make the dashboard useful.")

# ---------- Dashboard ----------
if page == "Dashboard":
    st.title("Welcome to your Student Success Hub 👋")
    st.write("Plan your learning, keep track of deadlines, and see your progress in one place.")
    tasks = query_df("SELECT * FROM tasks")
    grades = query_df("SELECT * FROM grades")
    goals = query_df("SELECT * FROM goals")
    today = date.today()
    pending = tasks[tasks["status"] != "Completed"] if not tasks.empty else tasks
    overdue_count = 0
    if not pending.empty:
        due = pd.to_datetime(pending["due_date"], errors="coerce").dt.date
        overdue_count = int(((due < today) & due.notna()).sum())
    completed_tasks = int((tasks["status"] == "Completed").sum()) if not tasks.empty else 0
    avg = (grades["score"] / grades["max_score"] * 100).mean() if not grades.empty else None
    open_goals = int((goals["completed"] == 0).sum()) if not goals.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pending tasks", len(pending))
    c2.metric("Overdue tasks", overdue_count)
    c3.metric("Average score", f"{avg:.1f}%" if avg is not None else "—")
    c4.metric("Active goals", open_goals)

    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("📌 Upcoming deadlines")
        if tasks.empty or pending.empty:
            st.success("You're all caught up, or you haven't added any tasks yet.")
        else:
            upcoming = pending.copy()
            upcoming["due_sort"] = pd.to_datetime(upcoming["due_date"], errors="coerce")
            upcoming = upcoming.sort_values("due_sort", na_position="last").head(6)
            upcoming["Due date"] = upcoming["due_date"].apply(safe_date)
            st.dataframe(upcoming[["title", "subject", "Due date", "priority", "status"]], use_container_width=True, hide_index=True)
    with right:
        st.subheader("📊 Grade snapshot")
        if grades.empty:
            st.info("Add assessment scores in Grades & Progress to see your results.")
        else:
            chart = grades.copy()
            chart["Percentage"] = (chart["score"] / chart["max_score"] * 100).round(1)
            by_subject = chart.groupby("subject", as_index=True)["Percentage"].mean().sort_values(ascending=False)
            st.bar_chart(by_subject)
    st.subheader("🗓️ Today's study timetable")
    today_name = date.today().strftime("%A")
    today_classes = query_df("SELECT * FROM timetable WHERE day = ? ORDER BY start_time", (today_name,))
    if today_classes.empty:
        st.caption(f"No classes saved for {today_name}. Add your weekly plan under Study Timetable.")
    else:
        st.dataframe(today_classes[["start_time", "end_time", "subject", "location"]], use_container_width=True, hide_index=True)
    st.caption(f"Today is {date.today().strftime('%A, %d %B %Y')}.")

# ---------- Tasks ----------
elif page == "Tasks & Assignments":
    st.title("📝 Tasks & Assignments")
    st.write("Capture assignments, revision tasks, and project deadlines.")
    with st.expander("➕ Add a task", expanded=True):
        with st.form("add_task", clear_on_submit=True):
            title = st.text_input("Task title *")
            c1, c2 = st.columns(2)
            subject = c1.text_input("Subject")
            due_date = c2.date_input("Due date", value=date.today() + timedelta(days=1))
            c3, c4 = st.columns(2)
            priority = c3.selectbox("Priority", ["Low", "Medium", "High"])
            status = c4.selectbox("Status", ["Pending", "In progress", "Completed"])
            notes = st.text_area("Details (optional)")
            submitted = st.form_submit_button("Save task", type="primary")
            if submitted:
                if not title.strip():
                    st.error("Please enter a task title.")
                else:
                    execute("INSERT INTO tasks(title, subject, due_date, priority, status, notes) VALUES (?, ?, ?, ?, ?, ?)",
                            (title.strip(), subject.strip(), due_date.isoformat(), priority, status, notes.strip()))
                    st.success("Task saved.")
                    st.rerun()

    tasks = query_df("SELECT * FROM tasks ORDER BY due_date")
    if not tasks.empty:
        f1, f2 = st.columns(2)
        status_filter = f1.selectbox("Filter by status", ["All", "Pending", "In progress", "Completed"])
        search = f2.text_input("Search tasks")
        filtered = tasks.copy()
        if status_filter != "All":
            filtered = filtered[filtered["status"] == status_filter]
        if search:
            filtered = filtered[filtered.apply(lambda row: search.lower() in " ".join(map(str, row.values)).lower(), axis=1)]
        display = filtered.copy()
        display["due_date"] = display["due_date"].apply(safe_date)
        st.dataframe(display[["id", "title", "subject", "due_date", "priority", "status", "notes"]], use_container_width=True, hide_index=True)
        st.subheader("Update or delete a task")
        task_options = {f"#{row.id} — {row.title} ({row.status})": int(row.id) for row in tasks.itertuples()}
        selected_label = st.selectbox("Choose task", list(task_options.keys()))
        selected_id = task_options[selected_label]
        selected = tasks[tasks["id"] == selected_id].iloc[0]
        with st.form("update_task"):
            new_status = st.selectbox("New status", ["Pending", "In progress", "Completed"],
                                      index=["Pending", "In progress", "Completed"].index(selected["status"]))
            col_a, col_b = st.columns(2)
            save = col_a.form_submit_button("Update status")
            delete = col_b.form_submit_button("Delete task")
            if save:
                execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, selected_id))
                st.success("Task updated.")
                st.rerun()
            if delete:
                execute("DELETE FROM tasks WHERE id = ?", (selected_id,))
                st.success("Task deleted.")
                st.rerun()
    else:
        st.info("No tasks yet. Add your first task above.")

# ---------- Timetable ----------
elif page == "Study Timetable":
    st.title("🗓️ Study Timetable")
    st.write("Build a reusable weekly timetable for classes or independent study.")
    with st.form("add_class", clear_on_submit=True):
        st.subheader("Add a class or study session")
        c1, c2 = st.columns(2)
        day = c1.selectbox("Day", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        subject = c2.text_input("Subject or activity *")
        c3, c4 = st.columns(2)
        start_time = c3.time_input("Start time", value=datetime.strptime("09:00", "%H:%M").time())
        end_time = c4.time_input("End time", value=datetime.strptime("10:00", "%H:%M").time())
        location = st.text_input("Room / location (optional)")
        add = st.form_submit_button("Add to timetable", type="primary")
        if add:
            if not subject.strip():
                st.error("Please enter a subject or activity.")
            elif end_time <= start_time:
                st.error("End time must be after start time.")
            else:
                execute("INSERT INTO timetable(day, start_time, end_time, subject, location) VALUES (?, ?, ?, ?, ?)",
                        (day, start_time.strftime("%H:%M"), end_time.strftime("%H:%M"), subject.strip(), location.strip()))
                st.success("Session added.")
                st.rerun()
    timetable = query_df("SELECT * FROM timetable ORDER BY CASE day WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 ELSE 7 END, start_time")
    if timetable.empty:
        st.info("Your timetable is empty.")
    else:
        chosen_day = st.selectbox("View day", ["All days", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        view = timetable if chosen_day == "All days" else timetable[timetable["day"] == chosen_day]
        st.dataframe(view[["day", "start_time", "end_time", "subject", "location"]], use_container_width=True, hide_index=True)
        st.download_button("Download timetable CSV", timetable.to_csv(index=False).encode("utf-8"), "study_timetable.csv", "text/csv")
        st.subheader("Remove a session")
        labels = {f"#{r.id} — {r.day} {r.start_time} {r.subject}": int(r.id) for r in timetable.itertuples()}
        selected = st.selectbox("Choose session to remove", list(labels.keys()))
        if st.button("Delete selected session"):
            execute("DELETE FROM timetable WHERE id = ?", (labels[selected],))
            st.success("Session deleted.")
            st.rerun()

# ---------- Grades ----------
elif page == "Grades & Progress":
    st.title("📈 Grades & Progress")
    st.write("Record assessment scores and review your progress. Percentages are calculated automatically.")
    with st.form("add_grade", clear_on_submit=True):
        c1, c2 = st.columns(2)
        subject = c1.text_input("Subject *")
        assessment = c2.text_input("Assessment name", placeholder="e.g. Test 1, Mock exam")
        c3, c4, c5 = st.columns(3)
        score = c3.number_input("Score earned", min_value=0.0, value=0.0, step=1.0)
        max_score = c4.number_input("Maximum score", min_value=1.0, value=100.0, step=1.0)
        assessment_date = c5.date_input("Assessment date", value=date.today())
        add = st.form_submit_button("Save score", type="primary")
        if add:
            if not subject.strip():
                st.error("Please enter a subject.")
            elif score > max_score:
                st.error("Score earned cannot be greater than the maximum score.")
            else:
                execute("INSERT INTO grades(subject, assessment, score, max_score, assessment_date) VALUES (?, ?, ?, ?, ?)",
                        (subject.strip(), assessment.strip(), score, max_score, assessment_date.isoformat()))
                st.success("Score saved.")
                st.rerun()
    grades = query_df("SELECT * FROM grades ORDER BY assessment_date DESC")
    if grades.empty:
        st.info("No scores recorded yet.")
    else:
        grades["Percentage"] = (grades["score"] / grades["max_score"] * 100).round(1)
        avg = grades["Percentage"].mean()
        best = grades["Percentage"].max()
        c1, c2, c3 = st.columns(3)
        c1.metric("Average percentage", f"{avg:.1f}%")
        c2.metric("Highest score", f"{best:.1f}%")
        c3.metric("Assessments", len(grades))
        st.bar_chart(grades.groupby("subject")["Percentage"].mean())
        shown = grades.copy()
        shown["assessment_date"] = shown["assessment_date"].apply(safe_date)
        st.dataframe(shown[["id", "subject", "assessment", "score", "max_score", "Percentage", "assessment_date"]], use_container_width=True, hide_index=True)
        st.download_button("Download grades CSV", grades.to_csv(index=False).encode("utf-8"), "grades.csv", "text/csv")
        grade_id = st.selectbox("Select a score to delete", grades["id"].tolist())
        if st.button("Delete selected score"):
            execute("DELETE FROM grades WHERE id = ?", (int(grade_id),))
            st.success("Score deleted.")
            st.rerun()

# ---------- Notes ----------
elif page == "Notes":
    st.title("📚 Study Notes")
    st.write("Keep concise revision notes and key ideas in one place.")
    with st.form("add_note", clear_on_submit=True):
        title = st.text_input("Note title *")
        subject = st.text_input("Subject")
        content = st.text_area("Your notes", height=180)
        save = st.form_submit_button("Save note", type="primary")
        if save:
            if not title.strip():
                st.error("Please provide a note title.")
            else:
                execute("INSERT INTO notes(title, subject, content) VALUES (?, ?, ?)", (title.strip(), subject.strip(), content.strip()))
                st.success("Note saved.")
                st.rerun()
    notes = query_df("SELECT * FROM notes ORDER BY updated_at DESC")
    if notes.empty:
        st.info("No notes saved yet.")
    else:
        search = st.text_input("Search notes")
        if search:
            notes = notes[notes.apply(lambda r: search.lower() in f"{r['title']} {r['subject']} {r['content']}".lower(), axis=1)]
        for row in notes.itertuples():
            with st.expander(f"{row.title} — {row.subject or 'General'}"):
                st.write(row.content or "_No content_")
                if st.button("Delete this note", key=f"delete_note_{row.id}"):
                    execute("DELETE FROM notes WHERE id = ?", (int(row.id),))
                    st.rerun()
        all_notes = query_df("SELECT title, subject, content, updated_at FROM notes")
        st.download_button("Export notes as CSV", all_notes.to_csv(index=False).encode("utf-8"), "study_notes.csv", "text/csv")

# ---------- Goals ----------
elif page == "Goals":
    st.title("🎯 Goals")
    st.write("Turn big ambitions into small, trackable goals.")
    with st.form("add_goal", clear_on_submit=True):
        title = st.text_input("Goal *", placeholder="e.g. Practise Mathematics for 20 minutes daily")
        target_date = st.date_input("Target date", value=date.today() + timedelta(days=7))
        add = st.form_submit_button("Add goal", type="primary")
        if add:
            if not title.strip():
                st.error("Please enter a goal.")
            else:
                execute("INSERT INTO goals(title, target_date) VALUES (?, ?)", (title.strip(), target_date.isoformat()))
                st.success("Goal added.")
                st.rerun()
    goals = query_df("SELECT * FROM goals ORDER BY completed, target_date")
    if goals.empty:
        st.info("No goals yet. Add one above.")
    else:
        for row in goals.itertuples():
            cols = st.columns([0.08, 0.72, 0.2])
            checked = cols[0].checkbox("Done", value=bool(row.completed), key=f"goal_{row.id}", label_visibility="collapsed")
            if checked != bool(row.completed):
                execute("UPDATE goals SET completed = ? WHERE id = ?", (int(checked), int(row.id)))
                st.rerun()
            label = f"~~{row.title}~~" if row.completed else row.title
            cols[1].markdown(f"{label}  \nTarget: {safe_date(row.target_date)}")
            if cols[2].button("Delete", key=f"del_goal_{row.id}"):
                execute("DELETE FROM goals WHERE id = ?", (int(row.id),))
                st.rerun()
        done = int((goals["completed"] == 1).sum())
        st.progress(done / len(goals), text=f"{done} of {len(goals)} goals completed")

# ---------- About ----------
elif page == "About":
    st.title("About Student Success Hub")
    st.markdown("""
    **Student Success Hub** is a portfolio-ready study organiser built with Python and Streamlit.

    **Included features**
    - Dashboard with task, grade, and goal summaries
    - Assignment and task tracking with due dates, priorities, and statuses
    - Weekly class and study timetable
    - Grade recording, percentage calculations, and charts
    - Searchable study notes
    - Personal goals and completion tracking
    - CSV exports for timetable and grades

    **Technology**
    - Streamlit for the user interface
    - SQLite for persistent local storage
    - Pandas for tables and summaries

    **Privacy note:** This starter version stores information in a local SQLite file on the machine running the app. It does not include login or cloud sync. If deploying for multiple users, add authentication and user-specific data isolation before using it with real student records.
    """)
    st.subheader("Portfolio improvement ideas")
    st.markdown("""
    1. Add user registration and secure login.
    2. Add exam countdowns and reminders.
    3. Add PDF report cards and printable timetables.
    4. Add backup and restore for the database.
    5. Deploy on Streamlit Community Cloud with a suitable persistent database.
    """)

st.sidebar.divider()
st.sidebar.caption("Student Success Hub • Built with Streamlit")
