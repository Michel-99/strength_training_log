"""Backfill: create one `session` row per (user, local day) of existing workouts.

Run from the repository root, e.g.:

    uv run python scripts/backfill_sessions.py --tz Europe/Vienna

Set DATABASE_URL to point at the target database (defaults to the local
strength_log.db). "Local day" depends on the time zone, so --tz is mandatory.

Idempotent: a (user, day) whose workout rows already carry a session_id is
skipped entirely, so rerunning after a successful run creates 0 sessions and
updates 0 rows. Rows with user_id IS NULL (legacy, no known owner) are only
counted, never assigned.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Session, Workout, db_manager  # noqa: E402
from app.timeutil import local_day, resolve_tz  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tz",
        required=True,
        help="IANA time zone name used to compute local days (e.g. Europe/Vienna)",
    )
    args = parser.parse_args()

    tz = resolve_tz(args.tz)
    if str(tz) == "UTC" and args.tz.strip().upper() != "UTC":
        print(f"warning: unknown time zone {args.tz!r}, falling back to UTC")

    db = db_manager()  # also ensures the `session` table and workout.session_id exist
    session = db.get_session()

    sessions_created = 0
    rows_updated = 0
    days_skipped = 0
    rows_skipped_no_user = 0

    try:
        rows = (
            session.query(Workout)
            .filter(Workout.user_id.isnot(None))
            .order_by(Workout.created_at.asc(), Workout.id.asc())
            .all()
        )
        rows_skipped_no_user = (
            session.query(Workout).filter(Workout.user_id.is_(None)).count()
        )

        # (user_id, local day) -> rows of that day
        by_day: dict[tuple[int, object], list[Workout]] = defaultdict(list)
        for row in rows:
            by_day[(row.user_id, local_day(row.created_at, tz))].append(row)

        for (user_id, day), day_rows in sorted(by_day.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            existing_ids = {r.session_id for r in day_rows if r.session_id is not None}
            if len(existing_ids) > 1:
                print(
                    f"warning: user {user_id} day {day} has rows pointing at multiple "
                    f"sessions {sorted(existing_ids)}; skipping this day"
                )
                days_skipped += 1
                continue
            if existing_ids and all(r.session_id is not None for r in day_rows):
                # Already backfilled: skip entirely (idempotency).
                days_skipped += 1
                continue

            if existing_ids:
                # Partially backfilled day: heal by linking the remaining rows
                # to the session the day already has.
                target_id = existing_ids.pop()
            else:
                start_time = min(r.created_at for r in day_rows)
                target = Session(
                    user_id=user_id,
                    source="manual",
                    activity_type="strength",
                    start_time=start_time,
                    end_time=None,
                )
                session.add(target)
                session.flush()
                target_id = target.id
                sessions_created += 1

            for r in day_rows:
                if r.session_id != target_id:
                    r.session_id = target_id
                    rows_updated += 1

        session.commit()
    finally:
        session.close()

    print("Backfill summary:")
    print(f"  sessions created:      {sessions_created}")
    print(f"  rows updated:          {rows_updated}")
    print(f"  days already linked:   {days_skipped}")
    print(f"  rows skipped (no user): {rows_skipped_no_user}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
