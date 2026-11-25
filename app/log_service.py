"""Logging workouts and reading back the most recent session."""

from datetime import timedelta
from typing import Dict, List

from app import analysis_service
from app.db import Session, Workout, get_db
from app.models import WorkoutBatchCreate, WorkoutCreate
from app.session_service import resolve_session_for_logging
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
        session.flush()  # populates the server-default created_at
        target = resolve_session_for_logging(
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
        target = resolve_session_for_logging(
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
    """The sets of the user's most recent session, grouped by exercise.

    The unit is the session entity, not the local day: with two sessions on
    one day the response contains only the last of them. Sets attach to the
    newest session of the day, so the newest Workout row identifies it. Its
    session metadata (rpe, notes) is returned alongside. Legacy rows that
    never got a session_id (pre-backfill) keep the old newest-local-day view.
    """
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
            return {
                "date": None,
                "session_id": None,
                "rpe": None,
                "notes": None,
                "exercises": [],
            }

        target = (
            session.query(Session)
            .filter(
                Session.id == newest.session_id,
                Session.user_id == user_id,
            )
            .first()
            if newest.session_id is not None
            else None
        )

        if target is not None:
            # All sets of that session; the day is the session's local day.
            rows = (
                session.query(Workout)
                .filter(
                    Workout.user_id == user_id,
                    Workout.session_id == target.id,
                )
                .order_by(Workout.created_at.asc(), Workout.id.asc())
                .all()
            )
            day = local_day(target.start_time, tz)
        else:
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
        # Progress is "first logged session -> this one", so the history is
        # bounded by this session's last set (not by the end of its day, so a
        # later same-day session is excluded).
        history = (
            session.query(Workout)
            .filter(
                Workout.user_id == user_id,
                Workout.exercise_name.in_(list(groups)),
                Workout.created_at <= rows[-1].created_at,
            )
            .all()
        )
        progress = analysis_service.calculate_progress_per_exercise(history, tz_name)
        for name, group in groups.items():
            group["change_pct"] = progress.get(name, {}).get("change_pct")
        return {
            "date": day.isoformat(),
            "session_id": target.id if target is not None else None,
            "rpe": target.rpe if target is not None else None,
            "notes": target.notes if target is not None else None,
            "exercises": list(groups.values()),
        }
    finally:
        session.close()
