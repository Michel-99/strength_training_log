import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict

from jose import jwt
from passlib.context import CryptContext

from app.db import db_manager, Workout, User
from app.models import WorkoutCreate, AuthRegister, AuthLogin

_db = db_manager()
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_jwt_secret = os.environ.get("JWT_SECRET_KEY", "change-this-secret-before-production")
_jwt_algorithm = "HS256"
_jwt_expire_minutes = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))
_bcrypt_max_password_bytes = 72


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _create_access_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=_jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, _jwt_secret, algorithm=_jwt_algorithm)


def _validate_password_length(password: str) -> None:
    if len(password.encode("utf-8")) > _bcrypt_max_password_bytes:
        raise ValueError("Password must be at most 72 bytes for bcrypt")


def register_user(data: AuthRegister) -> tuple[User, str]:
    session = _db.get_session()
    try:
        email = _normalize_email(data.email)
        _validate_password_length(data.password)
        existing = session.query(User).filter(User.email == email).first()
        if existing:
            raise ValueError("Email already registered")

        user = User(email=email, password_hash=_pwd_context.hash(data.password))
        session.add(user)
        session.commit()
        session.refresh(user)
        token = _create_access_token(user.id)
        return user, token
    finally:
        session.close()


def login_user(data: AuthLogin) -> tuple[User, str]:
    session = _db.get_session()
    try:
        email = _normalize_email(data.email)
        user = session.query(User).filter(User.email == email).first()
        if not user or not _pwd_context.verify(data.password, user.password_hash):
            raise PermissionError("Invalid email or password")

        token = _create_access_token(user.id)
        return user, token
    finally:
        session.close()


def get_user_from_token(token: str) -> User | None:
    session = _db.get_session()
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        return session.query(User).filter(User.id == int(user_id_str)).first()
    except Exception:
        return None
    finally:
        session.close()


# --- Workout Logic ---


def add_workout(data: WorkoutCreate, user_id: int) -> Workout:
    session = _db.get_session()
    try:
        entry = Workout(
            exercise_name=data.exercise_name,
            weight_kg=data.weight_kg,
            sets=data.sets,
            reps=data.reps,
            user_id=user_id,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry
    finally:
        session.close()


def get_workouts(user_id: int) -> List[Workout]:
    session = _db.get_session()
    try:
        return (
            session.query(Workout)
            .filter(Workout.user_id == user_id)
            .order_by(Workout.created_at.desc())
            .all()
        )
    finally:
        session.close()


def delete_workout(workout_id: int, user_id: int) -> bool:
    session = _db.get_session()
    try:
        entry = (
            session.query(Workout)
            .filter(Workout.id == workout_id, Workout.user_id == user_id)
            .first()
        )
        if not entry:
            return False
        session.delete(entry)
        session.commit()
        return True
    finally:
        session.close()


def get_exercises(user_id: int) -> List[str]:
    session = _db.get_session()
    try:
        rows = (
            session.query(Workout.exercise_name)
            .filter(Workout.user_id == user_id)
            .distinct()
            .order_by(Workout.exercise_name)
            .all()
        )
        return [r[0] for r in rows]
    finally:
        session.close()


def get_analysis_data(exercise: str, user_id: int) -> Dict:
    session = _db.get_session()
    try:
        rows = (
            session.query(Workout)
            .filter(Workout.exercise_name == exercise, Workout.user_id == user_id)
            .order_by(Workout.created_at.asc())
            .all()
        )
        labels = [r.created_at.strftime("%Y-%m-%d") for r in rows]
        data = [r.weight_kg for r in rows]
        return {"labels": labels, "data": data}
    finally:
        session.close()
