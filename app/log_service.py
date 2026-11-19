"""Logging workouts and reading back the most recent training day."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from app import analysis_service
from app.db import Session, Workout, get_db
from app.models import WorkoutBatchCreate, WorkoutCreate
from app.timeutil import (
    day_start_utc,
    local_day,
    next_day_start_utc,
    resolve_tz,
    today_local,
)

_db = get_db()


def _latest_session_of_day(db_session, user_id: int, tz_name: str) -> Session | None:
    """The most recently created session whose start_time is on the current local day."""
    tz = resolve_tz(tz_name)
    day = today_local(tz)
    return (
        db_session.query(Session)
        .filter(
            Session.user_id == user_id,
            Session.start_time >= day_start_utc(day, tz),
            Session.start_time < next_day_start_utc(day, tz),
        )
        .order_by(Session.created_at.desc(), Session.id.desc())
        .first()
    )


def _resolve_session(
    db_session, user_id: int, tz_name: str, new_session: bool, first_created_at: datetime
) -> Session:
    """Target session for a new log entry.

    Latest-session criterion: attach to the current local day's most recently
    created session if one exists, otherwise create one whose start_time is the
    first row's created_at. `new_session=True` always mints a fresh session.
    """
    target = None if new_session else _latest_session_of_day(db_session, user_id, tz_name)
    if target is None:
        target = Session(
            user_id=user_id,
            source="manual",
            activity_type="strength",
            start_time=first_created_at,
            end_time=None,
        )
        db_session.add(target)
        db_session.flush()
    return target


def start_session(user_id: int, tz_name: str = "UTC") -> Session:
    """Explicitly start a new session now (POST /sessions).

    The declared start_time is kept even when the first set attaches later;
    subsequent logging follows the latest-session criterion and lands here.
    """
    resolve_tz(tz_name)  # validated like everywhere else (unknown names fall back to UTC)
    session = _db.get_session()
    try:
        entry = Session(
            user_id=user_id,
            source="manual",
            activity_type="strength",
            start_time=datetime.now(timezone.utc),
            end_time=None,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry
    finally:
        session.close()


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
        session.flush()  # populates the server-default created_at
        target = _resolve_session(
            session, user_id, data.tz, data.new_session, entry.created_at
        )
        entry.session_id = target.id
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
        session.flush()  # populates the server-default created_at
        target = _resolve_session(
            session, user_id, data.tz, data.new_session, entries[0].created_at
        )
        for entry in entries:
            entry.session_id = target.id
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
