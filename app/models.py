from typing import List
from pydantic import BaseModel

# --- Pydantic Data Models (for validation) ---

class WorkoutBase(BaseModel):
    exercise_name: str
    weight_kg: float
    sets: int
    reps: int

class WorkoutCreate(WorkoutBase):
    pass

class WorkoutInDB(WorkoutBase):
    id: int
    log_date: int

class TipRequest(BaseModel):
    prompt: str

class TipResponse(BaseModel):
    tip: str

class AnalysisData(BaseModel):
    labels: List[str]
    data: List[float]
