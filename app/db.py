import os
import datetime
from sqlalchemy import create_engine, DateTime, String, Integer, Float, text
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
