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

    model_config = {"populate_by_name": True}


class WorkoutOut(BaseModel):
    id: int
    exercise_name: str
    weight_kg: float
    sets: int
    reps: int
    created_at: datetime

    @computed_field
    @property
    def log_date(self) -> int:
        """Unix timestamp expected by the frontend."""
        return int(self.created_at.timestamp())

    model_config = {"from_attributes": True}


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
    data: List[float]
