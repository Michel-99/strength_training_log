"""Per-exercise progress: one point per session (local day)."""

from typing import Dict, List

from app.db import Workout, get_db
from app.timeutil import day_start_utc, local_day, resolve_tz, today_local
from datetime import timedelta

_db = get_db()


def get_exercises(user_id: int) -> List[str]:
    session = _db.get_session()
    try:
        rows = (
            session.query(Workout.exercise_name)
            .filter(Workout.user_id == user_id)
            .distinct()
            .order_by(Workout.exercise_name)
            .all()
        )
        return [r[0] for r in rows]
    finally:
        session.close()


def get_analysis_data(
    exercise: str, user_id: int, days: int = 0, tz_name: str = "UTC"
) -> Dict:
    """Volume and heaviest weight per session for one exercise.

    `days` limits the result to the last N days (0 = everything).
    """
    tz = resolve_tz(tz_name)
    session = _db.get_session()
    try:
        query = session.query(Workout).filter(
            Workout.exercise_name == exercise, Workout.user_id == user_id
        )
        if days > 0:
            cutoff = today_local(tz) - timedelta(days=days)
            query = query.filter(Workout.created_at >= day_start_utc(cutoff, tz))
        rows = query.order_by(Workout.created_at.asc()).all()

        sessions: Dict[str, Dict[str, float]] = {}
        for r in rows:
            day = sessions.setdefault(
                local_day(r.created_at, tz).isoformat(),
                {"volume": 0.0, "max_weight": 0.0},
            )
            day["volume"] += r.weight_kg * r.sets * r.reps
            day["max_weight"] = max(day["max_weight"], r.weight_kg)

        labels = list(sessions)
        progress = calculate_progress_per_exercise(rows, tz_name).get(exercise, {})
        return {
            "change_pct": progress.get("change_pct"),
            "first_load": progress.get("first"),
            "last_load": progress.get("last"),
            "labels": labels,
            "volume": [sessions[d]["volume"] for d in labels],
            "max_weight": [sessions[d]["max_weight"] for d in labels],
        }
    finally:
        session.close()

def calculate_progress(
        user_id: int, days: int = 0, tz_name: str = "UTC"
        ) -> Dict[str, List[float]]:
    
    tz = resolve_tz(tz_name)
    session = _db.get_session()
    try:
            query = session.query(Workout).filter(
            Workout.user_id == user_id
            )
            if days > 0:
                cutoff = today_local(tz) - timedelta(days=days)
                query = query.filter(Workout.created_at >= day_start_utc(cutoff, tz))
            rows = query.order_by(Workout.created_at.asc()).all()
            return {}
    finally:
        session.close()

def query_all( user_id: int, days: int = 0, tz_name: str = "UTC") -> List[Workout]:
    tz = resolve_tz(tz_name)
    session = _db.get_session()

    try: 
        start_day = today_local(tz) - timedelta(days=days)   
        start = day_start_utc(start_day, tz)                  

        workouts = (
            session.query(Workout)
            .filter(Workout.user_id == user_id, Workout.created_at >= start)
            .all()
        )
        return workouts
    finally:
        session.close()

def calculate_progress_per_exercise(
    workouts: List[Workout], tz_name: str = "UTC"
) -> Dict[str, Dict[str, float | None]]:
    """Percentage change of the average load per rep, first vs last session.

    Per session (local day) the load is volume / reps, i.e. the
    rep-weighted average weight. Exercises with fewer than two sessions
    get `change_pct=None`.
    """
    tz = resolve_tz(tz_name)
    # exercise -> day -> [volume, reps]
    totals: Dict[str, Dict[str, List[float]]] = {}
    for w in sorted(workouts, key=lambda w: w.created_at):
        day = totals.setdefault(w.exercise_name, {}).setdefault(
            local_day(w.created_at, tz).isoformat(), [0.0, 0.0]
        )
        day[0] += w.weight_kg * w.sets * w.reps
        day[1] += w.sets * w.reps

    progress: Dict[str, Dict[str, float | None]] = {}
    for exercise, days in totals.items():
        loads = [vol / reps for vol, reps in days.values() if reps > 0]
        if not loads:
            continue
        first, last = loads[0], loads[-1]
        change = (
            (last - first) / first * 100
            if len(loads) > 1 and first > 0
            else None
        )
        progress[exercise] = {"first": first, "last": last, "change_pct": change}
    return progress
