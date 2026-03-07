import os
import datetime
from sqlalchemy import create_engine, DateTime, String, Integer, Float
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

    def get_session(self):
        """Returns a new database session."""
        return self.Session()
