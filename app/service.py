import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.db import User, get_db
from app.models import AuthRegister, AuthLogin

_db = get_db()
_pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

# Placeholder values that must never be used as the real JWT secret.
_PLACEHOLDER_SECRETS = {
    "change_me",
    "change-this-secret",
    "change-this-secret-before-production",
    "replace_with_a_long_random_secret",
}

_raw_secret = os.environ.get("JWT_SECRET_KEY", "").strip()
_is_production = os.environ.get("ENVIRONMENT", "").strip().lower() == "production"

if _raw_secret and _raw_secret.lower() not in _PLACEHOLDER_SECRETS:
    _jwt_secret = _raw_secret
elif _is_production:
    # Starting production with a missing or well-known secret would let
    # anyone forge valid tokens, so refuse to boot instead.
    raise RuntimeError(
        "JWT_SECRET_KEY is not set (or is a placeholder). Refusing to start "
        "in production. Set JWT_SECRET_KEY to a long random value, e.g. the "
        'output of: python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )
else:
    # Local development only: a random per-process secret. Tokens do not
    # survive a restart, which is acceptable locally.
    _jwt_secret = secrets.token_urlsafe(32)
    print(
        "WARNING: JWT_SECRET_KEY not set; using an ephemeral random secret "
        "for local development (logins reset on every restart)."
    )

_jwt_algorithm = "HS256"
_jwt_expire_minutes = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _create_access_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=_jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, _jwt_secret, algorithm=_jwt_algorithm)


def register_user(data: AuthRegister) -> tuple[User, str]:
    session = _db.get_session()
    try:
        email = _normalize_email(data.email)
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
