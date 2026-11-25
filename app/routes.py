import os

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import List

from app import (
    analysis_service,
    log_service,
    models,
    overview_service,
    polar_sync,
    ratelimit,
    service,
    session_service,
)
from app.polar import PolarClient, PolarError
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
def register(
    payload: models.AuthRegister, _: None = Depends(ratelimit.limit_auth)
):
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
def login(payload: models.AuthLogin, _: None = Depends(ratelimit.limit_auth)):
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
    return log_service.add_workout(workout, user.id)


@router.post("/workouts/batch", response_model=List[models.WorkoutOut], status_code=201)
def create_workout_sets(
    payload: models.WorkoutBatchCreate, user: User = Depends(get_current_user)
):
    """Logs one exercise with several sets (each with its own weight and reps)."""
    return log_service.add_workout_sets(payload, user.id)


@router.get("/workouts/latest", response_model=models.LatestWorkout)
def latest_workout(tz: str = "UTC", user: User = Depends(get_current_user)):
    """The most recent session (in the caller's time zone): its sets grouped
    by exercise, plus that session's RPE and notes."""
    return log_service.get_latest_workout(user.id, tz)


@router.get("/workouts", response_model=List[models.WorkoutOut])
def list_workouts(user: User = Depends(get_current_user)):
    """Returns all workouts ordered by most recent first."""
    return log_service.get_workouts(user.id)


@router.post("/sessions", response_model=models.SessionOut, status_code=201)
def start_session(
    payload: models.SessionCreate, user: User = Depends(get_current_user)
):
    """Explicitly starts a new training session now; later logging attaches to it."""
    return session_service.start_session(user.id, payload.tz)


@router.get("/sessions/current", response_model=models.SessionOut | None)
def current_session(tz: str = "UTC", user: User = Depends(get_current_user)):
    """The latest session of today (local day in `tz`), or null if none exists yet."""
    return session_service.get_current_session(user.id, tz)


@router.post("/sessions/current/feedback", response_model=models.SessionOut)
def current_session_feedback(
    payload: models.SessionFeedbackIn, user: User = Depends(get_current_user)
):
    """Find-or-create today's session and partially update its RPE/notes."""
    return session_service.save_current_feedback(user.id, payload)


@router.post(
    "/sessions/{session_id}/feedback", response_model=models.SessionOut
)
def session_feedback(
    session_id: int,
    payload: models.SessionFeedbackUpdate,
    user: User = Depends(get_current_user),
):
    """Repair endpoint: update RPE/notes of one of the caller's own sessions."""
    updated = session_service.save_feedback(user.id, session_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return updated


@router.delete("/workouts/{workout_id}", status_code=204)
def remove_workout(workout_id: int, user: User = Depends(get_current_user)):
    """Deletes a workout by its ID."""
    deleted = log_service.delete_workout(workout_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workout not found")


@router.get("/exercises", response_model=List[str])
def list_exercises(user: User = Depends(get_current_user)):
    """Returns a sorted list of unique exercise names."""
    return analysis_service.get_exercises(user.id)


@router.get("/analysis", response_model=models.AnalysisData)
def analysis(
    exercise: str,
    days: int = 0,
    tz: str = "UTC",
    user: User = Depends(get_current_user),
):
    """Volume and max weight per session for an exercise (days=0 means all time)."""
    return analysis_service.get_analysis_data(exercise, user.id, max(0, days), tz)


@router.get("/overview", response_model=models.OverviewData)
def overview(
    days: int = 30, tz: str = "UTC", user: User = Depends(get_current_user)
):
    """Strength, endurance and recovery per day, plus a 7-day summary."""
    return overview_service.get_overview(user.id, max(1, min(days, 90)), tz)


# --- Polar ---


def _polar_client() -> PolarClient:
    try:
        return PolarClient.from_env()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Polar is not configured")


@router.get("/polar/status")
def polar_status(user: User = Depends(get_current_user)):
    """Whether Polar is configured on the server and linked for this user."""
    configured = bool(
        os.environ.get("POLAR_CLIENT_ID") and os.environ.get("POLAR_CLIENT_SECRET")
    )
    return {"configured": configured, **polar_sync.get_status(user.id)}


@router.get("/polar/connect-url")
def polar_connect_url(user: User = Depends(get_current_user)):
    """URL the browser should open to let the user grant Polar access."""
    client = _polar_client()
    return {"url": client.authorization_url(state=polar_sync.create_state(user.id))}


@router.get("/polar/callback")
def polar_callback(code: str = "", state: str = "", error: str = ""):
    """Polar redirects here after the user approves (or denies) access."""
    user_id = polar_sync.read_state(state)
    if error or not code or user_id is None:
        return RedirectResponse("/?polar=denied#/analysis")

    client = _polar_client()
    try:
        token = client.exchange_code(code)
        client.register_user(token.access_token, member_id=str(user_id))
        polar_sync.save_connection(user_id, token)
        polar_sync.sync_user(client, user_id)
    except PolarError:
        return RedirectResponse("/?polar=error#/analysis")
    return RedirectResponse("/?polar=connected#/analysis")


@router.post("/polar/sync")
def polar_sync_now(user: User = Depends(get_current_user)):
    """Pull the latest Polar data into the database."""
    try:
        return polar_sync.sync_user(_polar_client(), user.id)
    except LookupError:
        raise HTTPException(status_code=400, detail="Polar is not connected")
    except PolarError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
