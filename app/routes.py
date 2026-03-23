from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import List

from app import models, service
from app.db import User

router = APIRouter()
auth_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> User:
    user = service.get_user_from_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


@router.post("/auth/register", response_model=models.AuthResponse, status_code=201)
def register(payload: models.AuthRegister):
    """Registers a new account and returns an access token."""
    try:
        user, token = service.register_user(payload)
        return models.AuthResponse(access_token=token, email=user.email)
    except ValueError as exc:
        detail = str(exc)
        if detail == "Email already registered":
            raise HTTPException(status_code=409, detail=detail)
        raise HTTPException(status_code=400, detail=detail)


@router.post("/auth/login", response_model=models.AuthResponse)
def login(payload: models.AuthLogin):
    """Authenticates with email/password and returns an access token."""
    try:
        user, token = service.login_user(payload)
        return models.AuthResponse(access_token=token, email=user.email)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/workouts", response_model=models.WorkoutOut, status_code=201)
def create_workout(
    workout: models.WorkoutCreate, user: User = Depends(get_current_user)
):
    """Logs a new workout entry."""
    return service.add_workout(workout, user.id)


@router.get("/workouts", response_model=List[models.WorkoutOut])
def list_workouts(user: User = Depends(get_current_user)):
    """Returns all workouts ordered by most recent first."""
    return service.get_workouts(user.id)


@router.delete("/workouts/{workout_id}", status_code=204)
def remove_workout(workout_id: int, user: User = Depends(get_current_user)):
    """Deletes a workout by its ID."""
    deleted = service.delete_workout(workout_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workout not found")


@router.get("/exercises", response_model=List[str])
def list_exercises(user: User = Depends(get_current_user)):
    """Returns a sorted list of unique exercise names."""
    return service.get_exercises(user.id)


@router.get("/analysis", response_model=models.AnalysisData)
def analysis(exercise: str, user: User = Depends(get_current_user)):
    """Returns weight progression data for a given exercise."""
    return service.get_analysis_data(exercise, user.id)


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
