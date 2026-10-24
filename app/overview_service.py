"""Overview page: strength, endurance and recovery side by side."""

from datetime import timedelta
from typing import Dict, List, Optional

from app.db import PolarExercise, PolarRecovery, PolarSleep, Workout, get_db
from app.timeutil import day_start_utc, local_day, resolve_tz, today_local

_db = get_db()

SUMMARY_DAYS = 7


def _average(values: List[float]) -> Optional[float]:
    return round(sum(values) / len(values), 1) if values else None


def _summary(days: List[Dict]) -> Dict:
    recent = days[-SUMMARY_DAYS:]
    charges = [d["ans_charge"] for d in recent if d["ans_charge"] is not None]
    sleeps = [d["sleep_score"] for d in recent if d["sleep_score"] is not None]
    return {
        "strength_sessions": sum(1 for d in recent if d["strength_volume"] > 0),
        "strength_volume_kg": round(sum(d["strength_volume"] for d in recent)),
        "endurance_hours": round(sum(d["endurance_minutes"] for d in recent) / 60, 1),
        "endurance_km": round(sum(d["endurance_km"] for d in recent), 1),
        "avg_ans_charge": _average(charges),
        "avg_sleep_score": _average(sleeps),
    }


def get_overview(user_id: int, days: int = 30, tz_name: str = "UTC") -> Dict:
    """Per-day numbers for the last `days` local days, plus a 7-day summary."""
    tz = resolve_tz(tz_name)
    start = today_local(tz) - timedelta(days=days - 1)
    start_dt = day_start_utc(start, tz)

    rows = {
        (start + timedelta(days=i)).isoformat(): {
            "date": (start + timedelta(days=i)).isoformat(),
            "strength_volume": 0.0,
            "strength_sets": 0,
            "endurance_minutes": 0.0,
            "endurance_km": 0.0,
            "endurance_load": 0.0,
            "ans_charge": None,
            "recharge_status": None,
            "hrv": None,
            "sleep_score": None,
        }
        for i in range(days)
    }

    session = _db.get_session()
    try:
        for w in (
            session.query(Workout)
            .filter(Workout.user_id == user_id, Workout.created_at >= start_dt)
            .all()
        ):
            day = rows.get(local_day(w.created_at, tz).isoformat())
            if day:
                day["strength_volume"] += w.weight_kg * w.sets * w.reps
                day["strength_sets"] += w.sets

        # Polar stores exercise start times as the watch's local time, so the
        # date is used as-is. Strength sessions on the watch are not endurance.
        for e in (
            session.query(PolarExercise)
            .filter(
                PolarExercise.user_id == user_id,
                PolarExercise.start_time >= start_dt - timedelta(days=1),
            )
            .all()
        ):
            if "STRENGTH" in (e.sport or "").upper():
                continue
            day = rows.get(e.start_time.date().isoformat())
            if day:
                day["endurance_minutes"] += (e.duration_seconds or 0) / 60
                day["endurance_km"] += (e.distance_m or 0) / 1000
                day["endurance_load"] += e.training_load or 0

        for r in (
            session.query(PolarRecovery)
            .filter(PolarRecovery.user_id == user_id, PolarRecovery.day >= start)
            .all()
        ):
            day = rows.get(r.day.isoformat())
            if day:
                day["ans_charge"] = r.ans_charge
                day["recharge_status"] = r.recharge_status
                day["hrv"] = r.avg_hrv

        for n in (
            session.query(PolarSleep)
            .filter(PolarSleep.user_id == user_id, PolarSleep.day >= start)
            .all()
        ):
            day = rows.get(n.day.isoformat())
            if day:
                day["sleep_score"] = n.sleep_score
    finally:
        session.close()

    day_list = list(rows.values())
    return {
        "days": day_list,
        "summary": _summary(day_list),
        "has_polar_data": any(
            d["endurance_minutes"] or d["ans_charge"] is not None for d in day_list
        ),
    }
