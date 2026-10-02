"""Fetch data from Polar and store it in the database (upserts, safe to re-run)."""

import datetime
import os
import re
from typing import Any, Callable, Dict, Optional

from jose import JWTError, jwt

from app.db import (
    PolarActivity,
    PolarConnection,
    PolarExercise,
    PolarRecovery,
    PolarSleep,
    db_manager,
)
from app.polar import PolarClient, PolarToken

_db = db_manager()

_DURATION = re.compile(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$")


def parse_duration(value: Any) -> Optional[int]:
    """ISO 8601 duration ("PT1H30M5S") -> seconds. Plain numbers pass through."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    match = _DURATION.match(str(value))
    if not match:
        return None
    days, hours, minutes, seconds = (float(g) if g else 0 for g in match.groups())
    return int(days * 86400 + hours * 3600 + minutes * 60 + seconds)


def parse_datetime(value: Any) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_date(value: Any) -> Optional[datetime.date]:
    parsed = parse_datetime(value)
    return parsed.date() if parsed else None


_state_secret = os.environ.get("JWT_SECRET_KEY", "change-this-secret-before-production")


def create_state(user_id: int) -> str:
    """Short-lived signed token carried through the OAuth redirect (CSRF protection)."""
    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
    payload = {"sub": str(user_id), "purpose": "polar", "exp": expires}
    return jwt.encode(payload, _state_secret, algorithm="HS256")


def read_state(state: str) -> Optional[int]:
    """Return the user id from a state token, or None if invalid/expired."""
    try:
        payload = jwt.decode(state, _state_secret, algorithms=["HS256"])
    except JWTError:
        return None
    if payload.get("purpose") != "polar":
        return None
    return int(payload["sub"])


def get_status(user_id: int) -> Dict[str, Any]:
    session = _db.get_session()
    try:
        conn = session.query(PolarConnection).filter_by(user_id=user_id).first()
        return {
            "connected": conn is not None,
            "last_synced_at": conn.last_synced_at.isoformat()
            if conn and conn.last_synced_at
            else None,
        }
    finally:
        session.close()


def save_connection(user_id: int, token: PolarToken) -> None:
    """Create or update the Polar link for an app user."""
    session = _db.get_session()
    try:
        conn = session.query(PolarConnection).filter_by(user_id=user_id).first()
        if conn is None:
            conn = PolarConnection(user_id=user_id)
            session.add(conn)
        conn.polar_user_id = token.user_id
        conn.access_token = token.access_token
        session.commit()
    finally:
        session.close()


def _upsert(session, model, lookup: Dict[str, Any], values: Dict[str, Any]) -> None:
    row = session.query(model).filter_by(**lookup).first()
    if row is None:
        row = model(**lookup)
        session.add(row)
    for key, value in values.items():
        setattr(row, key, value)


def _exercise_values(item: Dict) -> Dict[str, Any]:
    heart_rate = item.get("heart_rate") or {}
    return {
        "start_time": parse_datetime(item.get("start_time")),
        "sport": item.get("sport") or item.get("detailed_sport_info"),
        "duration_seconds": parse_duration(item.get("duration")),
        "distance_m": item.get("distance"),
        "calories": item.get("calories"),
        "avg_heart_rate": heart_rate.get("average"),
        "max_heart_rate": heart_rate.get("maximum"),
        "training_load": item.get("training_load"),
        "raw": item,
    }


def _activity_values(item: Dict) -> Dict[str, Any]:
    return {
        "steps": item.get("steps"),
        "calories": item.get("calories"),
        "active_calories": item.get("active_calories"),
        "active_seconds": parse_duration(item.get("active_duration")),
        "raw": item,
    }


def _sleep_values(item: Dict) -> Dict[str, Any]:
    return {
        "sleep_start": parse_datetime(item.get("sleep_start_time")),
        "sleep_end": parse_datetime(item.get("sleep_end_time")),
        "sleep_score": item.get("sleep_score"),
        "deep_seconds": parse_duration(item.get("deep_sleep")),
        "light_seconds": parse_duration(item.get("light_sleep")),
        "rem_seconds": parse_duration(item.get("rem_sleep")),
        "raw": item,
    }


def _recovery_values(item: Dict) -> Dict[str, Any]:
    return {
        "recharge_status": item.get("nightly_recharge_status"),
        "ans_charge": item.get("ans_charge"),
        "ans_charge_status": item.get("ans_charge_status"),
        "avg_heart_rate": item.get("heart_rate_avg"),
        "avg_hrv": item.get("heart_rate_variability_avg"),
        "avg_breathing_rate": item.get("breathing_rate_avg"),
        "raw": item,
    }


def _sync_items(
    user_id: int, model, items, key_of: Callable, values_of: Callable, key_name: str
) -> int:
    session = _db.get_session()
    try:
        count = 0
        for item in items:
            key = key_of(item)
            if key is None:
                continue
            _upsert(
                session, model, {"user_id": user_id, key_name: key}, values_of(item)
            )
            count += 1
        session.commit()
        return count
    finally:
        session.close()


def sync_user(client: PolarClient, user_id: int) -> Dict[str, int]:
    """Pull exercises, daily activity, sleep and recovery for one app user. Returns row counts."""
    session = _db.get_session()
    try:
        conn = session.query(PolarConnection).filter_by(user_id=user_id).first()
        if conn is None:
            raise LookupError("User has not connected Polar")
        token = conn.access_token
    finally:
        session.close()

    exercises = client.list_exercises(token, samples=False, zones=False, route=False)
    activities = client.list_activities(token)
    sleep = client.list_sleep(token)
    # list_sleep returns {"nights": [...]}; tolerate a bare list too.
    nights = sleep.get("nights", []) if isinstance(sleep, dict) else sleep

    recharge = client.list_nightly_recharge(token)
    recharges = recharge.get("recharges", []) if isinstance(recharge, dict) else recharge

    counts = {
        "exercises": _sync_items(
            user_id, PolarExercise, exercises,
            lambda i: i.get("id"), _exercise_values, "polar_id",
        ),
        "activities": _sync_items(
            user_id, PolarActivity, activities,
            lambda i: parse_date(i.get("start_time") or i.get("date")),
            _activity_values, "day",
        ),
        "sleep": _sync_items(
            user_id, PolarSleep, nights,
            lambda i: parse_date(i.get("date")), _sleep_values, "day",
        ),
        "recovery": _sync_items(
            user_id, PolarRecovery, recharges,
            lambda i: parse_date(i.get("date")), _recovery_values, "day",
        ),
    }

    session = _db.get_session()
    try:
        conn = session.query(PolarConnection).filter_by(user_id=user_id).first()
        conn.last_synced_at = datetime.datetime.now(datetime.timezone.utc)
        session.commit()
    finally:
        session.close()
    return counts
