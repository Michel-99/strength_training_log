"""Logging workouts and reading back the most recent training day."""

from datetime import timedelta
from typing import Dict, List

from app import analysis_service
from app.db import Workout, get_db
from app.models import WorkoutBatchCreate, WorkoutCreate
from app.timeutil import local_day, next_day_start_utc, day_start_utc, resolve_tz

_db = get_db()


def add_workout(data: WorkoutCreate, user_id: int) -> Workout:
    session = _db.get_session()
    try:
        entry = Workout(
            exercise_name=data.exercise_name.strip(),
            weight_kg=data.weight_kg,
            sets=data.sets,
            reps=data.reps,
            user_id=user_id,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry
    finally:
        session.close()


def add_workout_sets(data: WorkoutBatchCreate, user_id: int) -> List[Workout]:
    """Store each set as its own entry (sets=1) in a single transaction."""
    session = _db.get_session()
    try:
        exercise_name = data.exercise_name.strip()
        entries = [
            Workout(
                exercise_name=exercise_name,
                weight_kg=s.weight_kg,
                sets=1,
                reps=s.reps,
                set_number=i,
                rest_seconds=s.rest_seconds,
                user_id=user_id,
            )
            for i, s in enumerate(data.sets, start=1)
        ]
        session.add_all(entries)
        session.commit()
        for entry in entries:
            session.refresh(entry)
        return entries
    finally:
        session.close()


def get_workouts(user_id: int) -> List[Workout]:
    session = _db.get_session()
    try:
        return (
            session.query(Workout)
            .filter(Workout.user_id == user_id)
            .order_by(Workout.created_at.desc())
            .all()
        )
    finally:
        session.close()


def delete_workout(workout_id: int, user_id: int) -> bool:
    session = _db.get_session()
    try:
        entry = (
            session.query(Workout)
            .filter(Workout.id == workout_id, Workout.user_id == user_id)
            .first()
        )
        if not entry:
            return False
        session.delete(entry)
        session.commit()
        return True
    finally:
        session.close()


def get_latest_workout(user_id: int, tz_name: str = "UTC") -> Dict:
    """All sets of the user's most recent local day, grouped by exercise."""
    tz = resolve_tz(tz_name)
    session = _db.get_session()
    try:
        newest = (
            session.query(Workout)
            .filter(Workout.user_id == user_id)
            .order_by(Workout.created_at.desc(), Workout.id.desc())
            .first()
        )
        if newest is None:
            return {"date": None, "exercises": []}

        day = local_day(newest.created_at, tz)
        rows = (
            session.query(Workout)
            .filter(
                Workout.user_id == user_id,
                Workout.created_at >= day_start_utc(day, tz),
                Workout.created_at < next_day_start_utc(day, tz),
            )
            .order_by(Workout.created_at.asc(), Workout.id.asc())
            .all()
        )

        groups: Dict[str, Dict] = {}
        for w in rows:
            group = groups.setdefault(
                w.exercise_name,
                {
                    "exercise_name": w.exercise_name,
                    "total_sets": 0,
                    "volume_kg": 0.0,
                    "sets": [],
                },
            )
            group["total_sets"] += w.sets
            group["volume_kg"] += w.weight_kg * w.sets * w.reps
            group["sets"].append(
                {
                    "id": w.id,
                    "set_number": w.set_number or len(group["sets"]) + 1,
                    "sets": w.sets,
                    "reps": w.reps,
                    "weight_kg": w.weight_kg,
                    "rest_seconds": w.rest_seconds,
                }
            )
        history = (
            session.query(Workout)
            .filter(
                Workout.user_id == user_id,
                Workout.exercise_name.in_(list(groups)),
                Workout.created_at < next_day_start_utc(day, tz),
            )
            .all()
        )
        progress = analysis_service.calculate_progress_per_exercise(history, tz_name)
        for name, group in groups.items():
            group["change_pct"] = progress.get(name, {}).get("change_pct")
        return {"date": day.isoformat(), "exercises": list(groups.values())}
    finally:
        session.close()
