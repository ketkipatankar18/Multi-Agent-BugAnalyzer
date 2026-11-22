"""
auth.py
-------
Reviewer authentication for BugAnalyzer.

- Passwords: bcrypt hashes (salted, deliberately slow) — never stored in plain text.
- Sessions: a signed JWT (HS256) in an httpOnly cookie. JavaScript can't read it
  (XSS-safe); the browser sends it automatically with each request.
- Roles: admin (approve/reject, audit data) and viewer (read-only queue).
- Every request re-checks the user in the DB, so deactivating someone or
  changing their role takes effect on their next request.
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response

import db
from logger import get_logger

log = get_logger(__name__)

COOKIE_NAME   = "ba_session"
SESSION_HOURS = int(os.environ.get("SESSION_HOURS", "8"))
ROLES         = ("admin", "viewer")


def _secret() -> str:
    secret = os.environ.get("AUTH_JWT_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError(
            "AUTH_JWT_SECRET must be set to a random string of 32+ characters. "
            'Generate one: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    return secret

_secret()   # fail fast at startup, not on the first login


# ── Passwords ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


# Compared against when the username doesn't exist, so "unknown user" and
# "wrong password" take the same time — attackers can't probe for usernames.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


def authenticate(username: str, password: str) -> dict | None:
    user = db.get_user(username.strip().lower())
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user["password_hash"]) or not user["is_active"]:
        return None
    return user


# ── Session cookie ────────────────────────────────────────────────────────────

def _cookie_settings() -> dict:
    return {
        "httponly": True,
        "secure"  : os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        "samesite": os.environ.get("COOKIE_SAMESITE", "lax").lower(),
        "path"    : "/",
    }


def issue_session(response: Response, user: dict) -> None:
    now   = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub" : user["username"],
            "role": user["role"],
            "iat" : now,
            "exp" : now + timedelta(hours=SESSION_HOURS),
        },
        _secret(),
        algorithm="HS256",
    )
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_HOURS * 3600, **_cookie_settings())


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, **_cookie_settings())


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def get_optional_user(request: Request) -> dict | None:
    """The logged-in user, or None. Never raises."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    user = db.get_user(payload.get("sub", ""))
    if user is None or not user["is_active"]:
        return None
    # Role comes from the DB, not the token — role changes apply immediately
    return {"username": user["username"], "role": user["role"]}


def get_current_user(user: dict | None = Depends(get_optional_user)) -> dict:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_role(*roles: str):
    """Usage: user: dict = Depends(require_role("admin"))"""
    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker