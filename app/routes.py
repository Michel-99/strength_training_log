from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app import models, service, db

# Create a 'router'
# This is like a 'Blueprint' in Flask
router = APIRouter()

# Dependency for database connection
DBConnection = Depends(db.get_db_connection)

@router.get("/workouts", response_model=List[models.WorkoutInDB])
def get_workouts(conn = DBConnection):
    """Fetches all workouts from the database."""
    try:
        return service.logic_get_workouts(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workouts", response_model=models.WorkoutInDB)
def add_workout(workout: models.WorkoutCreate, conn = DBConnection):
    """Adds a new workout to the database."""
    try:
        return service.logic_add_workout(conn, workout)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/workouts/{workout_id}")
def delete_workout(workout_id: int, conn = DBConnection):
    """Deletes a workout by its ID."""
    try:
        rowcount = service.logic_delete_workout(conn, workout_id)
        if rowcount == 0:
            raise HTTPException(status_code=404, detail="Workout not found")
        return {"message": "Workout deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-tip", response_model=models.TipResponse)
def generate_tip(req: models.TipRequest):
    """Generates an AI tip based on a prompt."""
    try:
        tip = service.logic_get_ai_tip(req.prompt)
        return models.TipResponse(tip=tip)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/exercises", response_model=List[str])
def get_exercises(conn = DBConnection):
    """Fetches a list of unique exercise names."""
    try:
        return service.logic_get_exercises(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analysis", response_model=models.AnalysisData)
def get_analysis_data(exercise: str, conn = DBConnection):
    """Fetches weight progression data for a specific exercise."""
    try:
        return service.logic_get_analysis_data(conn, exercise)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
