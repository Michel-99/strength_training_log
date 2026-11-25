from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, computed_field
from pydantic import AliasChoices


# --- Pydantic Data Models (for validation) ---


class WorkoutCreate(BaseModel):
    # Accept both the frontend short names ("exercise", "weight")
    # and the internal names ("exercise_name", "weight_kg")
    exercise_name: str = Field(
        validation_alias=AliasChoices("exercise", "exercise_name")
    )
    weight_kg: float = Field(validation_alias=AliasChoices("weight", "weight_kg"))
    sets: int
    reps: int
    # Local-day resolution for attaching the row to a session; old clients
    # that don't send it keep working (UTC).
    tz: str = "UTC"
    # When true, always start a fresh session for this entry instead of
    # attaching to the current local day's latest session.
    new_session: bool = False

    model_config = {"populate_by_name": True}


class SetCreate(BaseModel):
    weight_kg: float = Field(validation_alias=AliasChoices("weight", "weight_kg"))
    reps: int = Field(ge=1)
    rest_seconds: int | None = Field(default=None, ge=0, le=86400)

    model_config = {"populate_by_name": True}


class WorkoutBatchCreate(BaseModel):
    """One exercise with one or more sets, each with its own weight and reps."""

    exercise_name: str = Field(
        validation_alias=AliasChoices("exercise", "exercise_name")
    )
    sets: List[SetCreate] = Field(min_length=1)
    # Local-day resolution for attaching the rows to a session; old clients
    # that don't send it keep working (UTC).
    tz: str = "UTC"
    # When true, always start a fresh session for this batch instead of
    # attaching to the current local day's latest session.
    new_session: bool = False

    model_config = {"populate_by_name": True}


class SessionCreate(BaseModel):
    """Body of POST /sessions: explicitly start a new session now."""

    tz: str = "UTC"


class SessionOut(BaseModel):
    id: int
    user_id: int
    source: str
    external_id: str | None = None
    activity_type: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    rpe: int | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionFeedbackIn(BaseModel):
    """Body of POST /sessions/current/feedback.

    Partial-update semantics: a field left out (or null) keeps the stored
    value; an explicit "" for notes clears it.
    """

    tz: str = "UTC"  # IANA name; determines "current day"
    rpe: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = Field(default=None, max_length=2000)


class SessionFeedbackUpdate(BaseModel):
    """Body of POST /sessions/{session_id}/feedback (repair endpoint; no tz)."""

    rpe: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = Field(default=None, max_length=2000)


class WorkoutOut(BaseModel):
    id: int
    exercise_name: str
    weight_kg: float
    sets: int
    reps: int
    set_number: int | None = None
    rest_seconds: int | None = None
    created_at: datetime

    @computed_field
    @property
    def log_date(self) -> int:
        """Unix timestamp expected by the frontend."""
        return int(self.created_at.timestamp())

    model_config = {"from_attributes": True}


class SetOut(BaseModel):
    id: int
    set_number: int
    sets: int
    reps: int
    weight_kg: float
    rest_seconds: int | None = None


class ExerciseGroup(BaseModel):
    exercise_name: str
    total_sets: int
    volume_kg: float
    # % change of avg weight per rep, first logged session -> this one.
    change_pct: float | None = None
    sets: List[SetOut]


class LatestWorkout(BaseModel):
    """The user's most recent session, with its sets grouped per exercise."""

    date: str | None = None
    # Metadata of that session; None when no session exists (legacy rows only).
    session_id: int | None = None
    rpe: int | None = None
    notes: str | None = None
    exercises: List[ExerciseGroup] = []


class OverviewDay(BaseModel):
    date: str
    strength_volume: float
    strength_sets: int
    endurance_minutes: float
    endurance_km: float
    endurance_load: float
    ans_charge: float | None = None
    recharge_status: int | None = None
    hrv: float | None = None
    sleep_score: float | None = None


class OverviewSummary(BaseModel):
    """Totals for the last 7 days of the requested range."""

    strength_sessions: int
    strength_volume_kg: float
    endurance_hours: float
    endurance_km: float
    avg_ans_charge: float | None = None
    avg_sleep_score: float | None = None


class OverviewData(BaseModel):
    days: List[OverviewDay]
    summary: OverviewSummary
    has_polar_data: bool


class AuthRegister(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class AuthLogin(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


class AnalysisData(BaseModel):
    labels: List[str]
    volume: List[float]
    max_weight: List[float]
    # Avg weight per rep (volume / reps), first vs last session in range.
    change_pct: float | None = None
    first_load: float | None = None
    last_load: float | None = None
