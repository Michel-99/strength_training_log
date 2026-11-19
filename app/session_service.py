"""Session entity operations: find-or-create per local day, current session, feedback.

This module owns the canonical "latest session of the current local day"
find-or-create logic. `log_service` uses the same `resolve_session_for_logging`
when attaching workout rows, so feedback always lands on the session the next
batch will attach to.
"""

from datetime import datetime, timezone

from app.db import Session, Workout, get_db
from app.models import SessionFeedbackIn, SessionFeedbackUpdate
from app.timeutil import day_start_utc, next_day_start_utc, resolve_tz, today_local

_db = get_db()


def latest_session_of_day(db_session, user_id: int, tz_name: str) -> Session | None:
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


def get_or_create_today_session(db_session, user_id: int, tz_name: str) -> Session:
    """Find-or-create the latest session of the current local day.

    A session minted here carries a provisional start_time (now); when the
    first set attaches, `resolve_session_for_logging` re-stamps start_time with
    that set's timestamp unless the session was explicitly declared via
    POST /sessions.
    """
    target = latest_session_of_day(db_session, user_id, tz_name)
    if target is None:
        target = Session(
            user_id=user_id,
            source="manual",
            activity_type="strength",
            start_time=datetime.now(timezone.utc),
            end_time=None,
        )
        db_session.add(target)
        db_session.flush()
    return target


def _session_has_sets(db_session, session_id: int) -> bool:
    return (
        db_session.query(Workout.id)
        .filter(Workout.session_id == session_id)
        .first()
        is not None
    )


def resolve_session_for_logging(
    db_session,
    user_id: int,
    tz_name: str,
    new_session: bool,
    first_created_at: datetime,
) -> Session:
    """Target session for a new log entry.

    Latest-session criterion: attach to the current local day's most recently
    created session if one exists, otherwise create one whose start_time is the
    first row's created_at. `new_session=True` always mints a fresh session.
    An existing session that has no sets yet and was not explicitly declared
    (e.g. created via the feedback endpoint) gets its provisional start_time
    re-stamped with the first set's timestamp.
    """
    target = (
        None if new_session else latest_session_of_day(db_session, user_id, tz_name)
    )
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
    elif not target.start_time_declared and not _session_has_sets(db_session, target.id):
        target.start_time = first_created_at
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
            start_time_declared=True,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry
    finally:
        session.close()


def get_current_session(user_id: int, tz_name: str = "UTC") -> Session | None:
    """The latest session of today (local day in `tz`), or None. Read-only."""
    session = _db.get_session()
    try:
        return latest_session_of_day(session, user_id, tz_name)
    finally:
        session.close()


def _apply_feedback(target: Session, rpe: int | None, notes: str | None) -> None:
    """Partial update: None leaves the stored value; explicit "" clears notes."""
    if rpe is not None:
        target.rpe = rpe
    if notes is not None:
        target.notes = notes if notes != "" else None


def save_current_feedback(user_id: int, data: SessionFeedbackIn) -> Session:
    """Find-or-create today's session, then apply the feedback to it."""
    session = _db.get_session()
    try:
        target = get_or_create_today_session(session, user_id, data.tz)
        _apply_feedback(target, data.rpe, data.notes)
        session.commit()
        session.refresh(target)
        return target
    finally:
        session.close()


def save_feedback(
    user_id: int, session_id: int, data: SessionFeedbackUpdate
) -> Session | None:
    """Repair endpoint: update an arbitrary session owned by the caller.

    Returns None if the session does not exist or belongs to another user.
    """
    session = _db.get_session()
    try:
        target = (
            session.query(Session)
            .filter(Session.id == session_id, Session.user_id == user_id)
            .first()
        )
        if target is None:
            return None
        _apply_feedback(target, data.rpe, data.notes)
        session.commit()
        session.refresh(target)
        return target
    finally:
        session.close()
