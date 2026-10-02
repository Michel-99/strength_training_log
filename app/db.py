import os
import datetime
from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.sql import func

# Render provides DATABASE_URL as "postgres://..." but SQLAlchemy requires "postgresql://"
_raw_url = os.environ.get("DATABASE_URL", "sqlite:///strength_log.db")
DEFAULT_DB_URL = _raw_url.replace("postgres://", "postgresql://", 1)


class Base(DeclarativeBase):
    pass


class Workout(Base):
    __tablename__ = "workout"

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_name: Mapped[str] = mapped_column(String)
    weight_kg: Mapped[float] = mapped_column(Float)
    sets: Mapped[int] = mapped_column(Integer)
    reps: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class User(Base):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Excercise(Base):
    __tablename__ = "excerices"

    id: Mapped[int] = mapped_column(primary_key=True)
    excercise_name: Mapped[str] = mapped_column(String(120))
    body_region: Mapped[str] = mapped_column(String(40))


class PolarConnection(Base):
    """Links one app user to their Polar account (one row per user)."""

    __tablename__ = "polar_connection"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), unique=True, index=True
    )
    polar_user_id: Mapped[int] = mapped_column(BigInteger)
    access_token: Mapped[str] = mapped_column(String(255))
    last_synced_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PolarExercise(Base):
    """A training session recorded on a Polar device."""

    __tablename__ = "polar_exercise"
    __table_args__ = (UniqueConstraint("user_id", "polar_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    polar_id: Mapped[str] = mapped_column(String(64))
    start_time: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    sport: Mapped[str | None] = mapped_column(String(80), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    training_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON)  # full Polar payload


class PolarActivity(Base):
    """Daily activity summary (steps, calories, ...)."""

    __tablename__ = "polar_activity"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[datetime.date] = mapped_column(Date, index=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON)


class PolarSleep(Base):
    """One night of sleep."""

    __tablename__ = "polar_sleep"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[datetime.date] = mapped_column(Date, index=True)
    sleep_start: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sleep_end: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sleep_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    deep_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    light_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rem_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON)


class PolarRecovery(Base):
    """Nightly Recharge: how well the body recovered overnight."""

    __tablename__ = "polar_recovery"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[datetime.date] = mapped_column(Date, index=True)
    recharge_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ans_charge: Mapped[float | None] = mapped_column(Float, nullable=True)
    ans_charge_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_heart_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_hrv: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_breathing_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON)


class db_manager:
    def __init__(self, db_url: str = DEFAULT_DB_URL) -> None:
        self.DATABASE_URL = db_url
        self.engine = create_engine(self.DATABASE_URL)
        self.initialize_tables()
        self.Session = sessionmaker(bind=self.engine)

    def initialize_tables(self):
        """Creates all tables if they don't already exist."""
        Base.metadata.create_all(self.engine)
        self.ensure_workout_user_id_column()

    def ensure_workout_user_id_column(self):
        """Adds workout.user_id if missing in pre-existing databases."""
        dialect = self.engine.dialect.name

        with self.engine.begin() as conn:
            if dialect == "sqlite":
                result = conn.execute(text("PRAGMA table_info(workout)"))
                columns = {row[1] for row in result.fetchall()}
                if "user_id" not in columns:
                    conn.execute(text("ALTER TABLE workout ADD COLUMN user_id INTEGER"))
            elif dialect in {"postgresql", "postgres"}:
                result = conn.execute(
                    text(
                        """
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = 'workout'
                          AND column_name = 'user_id'
                        """
                    )
                ).first()
                if result is None:
                    conn.execute(text("ALTER TABLE workout ADD COLUMN user_id INTEGER"))

    def get_session(self):
        """Returns a new database session."""
        return self.Session()
