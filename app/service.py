from datetime import datetime
from typing import List, Dict, Any

from app.db import db_manager, Workout
from app.models import WorkoutCreate

_db = db_manager()


# --- Workout Logic ---


def add_workout(data: WorkoutCreate) -> Workout:
    session = _db.get_session()
    try:
        entry = Workout(
            exercise_name=data.exercise_name,
            weight_kg=data.weight_kg,
            sets=data.sets,
            reps=data.reps,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry
    finally:
        session.close()


def get_workouts() -> List[Workout]:
    session = _db.get_session()
    try:
        return session.query(Workout).order_by(Workout.created_at.desc()).all()
    finally:
        session.close()


def delete_workout(workout_id: int) -> bool:
    session = _db.get_session()
    try:
        entry = session.query(Workout).filter(Workout.id == workout_id).first()
        if not entry:
            return False
        session.delete(entry)
        session.commit()
        return True
    finally:
        session.close()


def get_exercises() -> List[str]:
    session = _db.get_session()
    try:
        rows = (
            session.query(Workout.exercise_name)
            .distinct()
            .order_by(Workout.exercise_name)
            .all()
        )
        return [r[0] for r in rows]
    finally:
        session.close()


def get_analysis_data(exercise: str) -> Dict:
    session = _db.get_session()
    try:
        rows = (
            session.query(Workout)
            .filter(Workout.exercise_name == exercise)
            .order_by(Workout.created_at.asc())
            .all()
        )
        labels = [r.created_at.strftime("%Y-%m-%d") for r in rows]
        data = [r.weight_kg for r in rows]
        return {"labels": labels, "data": data}
    finally:
        session.close()


def logic_get_workouts(conn) -> List[Dict[str, Any]]:
    """Fetches all workouts from the database."""
    is_postgres = not isinstance(conn, sqlite3.Connection)

    if is_postgres:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workout ORDER BY log_date DESC")
        workouts_rows = cursor.fetchall()
        desc = cursor.description
        cursor.close()
    else:  # SQLite
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workout ORDER BY log_date DESC")
        workouts_rows = cursor.fetchall()
        desc = None  # Not needed for sqlite helper

    return [workout_row_to_dict(row, desc) for row in workouts_rows]


def logic_add_workout(conn, workout) -> Dict[str, Any]:
    """Adds a new workout to the database."""
    is_postgres = not isinstance(conn, sqlite3.Connection)

    if is_postgres:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO workout (exercise_name, weight_kg, sets, reps, log_date) 
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, log_date
            """,
            (
                workout.exercise_name,
                workout.weight_kg,
                workout.sets,
                workout.reps,
                int(time.time()),
            ),
        )
        new_id, log_date = cursor.fetchone()
        conn.commit()
        cursor.close()
    else:  # SQLite
        cursor = conn.cursor()
        log_date = int(time.time())
        cursor.execute(
            "INSERT INTO workout (exercise_name, weight_kg, sets, reps, log_date) VALUES (?, ?, ?, ?, ?)",
            (
                workout.exercise_name,
                workout.weight_kg,
                workout.sets,
                workout.reps,
                log_date,
            ),
        )
        new_id = cursor.lastrowid
        conn.commit()

    return {"id": new_id, "log_date": log_date, **workout.dict()}


def logic_delete_workout(conn, workout_id: int) -> int:
    """Deletes a workout by its ID. Returns rowcount."""
    is_postgres = not isinstance(conn, sqlite3.Connection)

    cursor = conn.cursor()
    if is_postgres:
        cursor.execute("DELETE FROM workout WHERE id = %s", (workout_id,))
    else:  # SQLite
        cursor.execute("DELETE FROM workout WHERE id = ?", (workout_id,))

    rowcount = cursor.rowcount
    conn.commit()
    cursor.close()
    return rowcount


# --- Analysis Logic ---


def logic_get_exercises(conn) -> List[str]:
    """Fetches a list of unique exercise names."""
    is_postgres = not isinstance(conn, sqlite3.Connection)

    cursor = conn.cursor()
    if is_postgres:
        cursor.execute(
            "SELECT DISTINCT exercise_name FROM workout ORDER BY exercise_name"
        )
    else:  # SQLite
        cursor.execute(
            "SELECT DISTINCT exercise_name FROM workout ORDER BY exercise_name"
        )

    exercises = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return exercises


def logic_get_analysis_data(conn, exercise: str) -> Dict[str, List]:
    """Fetches weight progression data for a specific exercise."""
    is_postgres = not isinstance(conn, sqlite3.Connection)

    cursor = conn.cursor()
    if is_postgres:
        cursor.execute(
            "SELECT log_date, weight_kg FROM workout WHERE exercise_name = %s ORDER BY log_date ASC",
            (exercise,),
        )
    else:  # SQLite
        cursor.execute(
            "SELECT log_date, weight_kg FROM workout WHERE exercise_name = ? ORDER BY log_date ASC",
            (exercise,),
        )

    data_rows = cursor.fetchall()
    cursor.close()

    # Format data for Chart.js
    labels = [datetime.fromtimestamp(row[0]).strftime("%Y-%m-%d") for row in data_rows]
    data = [float(row[1]) for row in data_rows]

    return {"labels": labels, "data": data}
