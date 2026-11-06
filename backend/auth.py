"""密码哈希和 Cookie 会话。浏览器只拿到 session_id，拿不到密码。"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, Request, Response

from database import connect

COOKIE = "session_id"
PBKDF2_ROUNDS = 120_000


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS)
    return f"{salt}${digest.hex()}"


def verify_password(password, stored):
    if not stored or "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    return secrets.compare_digest(hash_password(password, salt).split("$", 1)[1], digest)


def public_user(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "createdAt": row["created_at"],
    }


def create_session(user_id):
    session_id = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(days=14)).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, ?)",
            (session_id, user_id, expires),
        )
    return session_id


def set_session_cookie(response: Response, session_id: str):
    response.set_cookie(COOKIE, session_id, httponly=True, samesite="lax", max_age=14 * 24 * 3600, path="/")


def clear_session_cookie(response: Response):
    response.delete_cookie(COOKIE, path="/")


def user_from_request(request: Request):
    session_id = request.cookies.get(COOKIE)
    if not session_id:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT users.* FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.session_id = ? AND sessions.expires_at > ?
            """,
            (session_id, datetime.utcnow().isoformat(timespec="seconds")),
        ).fetchone()
    return public_user(row) if row else None


def require_user(request: Request):
    user = user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")
    return user


def allowed_origins():
    raw = os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000,http://127.0.0.1:3000",
    )
    return [item.strip() for item in raw.split(",") if item.strip()]
