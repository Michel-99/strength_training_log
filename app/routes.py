from fastapi import APIRouter, HTTPException
from typing import List

from app import models, service

router = APIRouter()


@router.post("/workouts", response_model=models.WorkoutOut, status_code=201)
def create_workout(workout: models.WorkoutCreate):
    """Logs a new workout entry."""
    return service.add_workout(workout)


@router.get("/workouts", response_model=List[models.WorkoutOut])
def list_workouts():
    """Returns all workouts ordered by most recent first."""
    return service.get_workouts()


@router.delete("/workouts/{workout_id}", status_code=204)
def remove_workout(workout_id: int):
    """Deletes a workout by its ID."""
    deleted = service.delete_workout(workout_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workout not found")


@router.get("/exercises", response_model=List[str])
def list_exercises():
    """Returns a sorted list of unique exercise names."""
    return service.get_exercises()


@router.get("/analysis", response_model=models.AnalysisData)
def analysis(exercise: str):
    """Returns weight progression data for a given exercise."""
    return service.get_analysis_data(exercise)


# @router.delete("/workouts/{workout_id}")
# def delete_workout(workout_id: int, conn = DBConnection):
#     """Deletes a workout by its ID."""
#     try:
#         rowcount = service.logic_delete_workout(conn, workout_id)
#         if rowcount == 0:
#             raise HTTPException(status_code=404, detail="Workout not found")
#         return {"message": "Workout deleted"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/generate-tip", response_model=models.TipResponse)
# def generate_tip(req: models.TipRequest):
#     """Generates an AI tip based on a prompt."""
#     try:
#         tip = service.logic_get_ai_tip(req.prompt)
#         return models.TipResponse(tip=tip)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/exercises", response_model=List[str])
# def get_exercises(conn = DBConnection):
#     """Fetches a list of unique exercise names."""
#     try:
#         return service.logic_get_exercises(conn)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/analysis", response_model=models.AnalysisData)
# def get_analysis_data(exercise: str, conn = DBConnection):
#     """Fetches weight progression data for a specific exercise."""
#     try:
#         return service.logic_get_analysis_data(conn, exercise)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
