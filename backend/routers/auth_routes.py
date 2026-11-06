"""注册、登录、退出、当前用户、管理员看用户。"""

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response

from auth import (
    clear_session_cookie,
    create_session,
    hash_password,
    public_user,
    require_user,
    set_session_cookie,
    verify_password,
)
from database import connect
from schemas import LoginIn, NameIn, RegisterIn

router = APIRouter(prefix="/api")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def now():
    return datetime.utcnow().isoformat(timespec="seconds")


@router.post("/auth/register")
def register(body: RegisterIn, response: Response):
    email = body.email.strip().lower()
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="NAME_REQUIRED")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="BAD_EMAIL")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="SHORT_PASSWORD")
    with connect() as conn:
        exists = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail="EMAIL_TAKEN")
        count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        role = "admin" if count == 0 else "member"
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, hash_password(body.password), role, now()),
        )
        user = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    set_session_cookie(response, create_session(user["id"]))
    return public_user(user)


@router.post("/auth/login")
def login(body: LoginIn, response: Response):
    email = body.email.strip().lower()
    with connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="BAD_LOGIN")
    set_session_cookie(response, create_session(user["id"]))
    return public_user(user)


@router.post("/auth/logout")
def logout(response: Response, user=Depends(require_user)):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/auth/me")
def me(user=Depends(require_user)):
    return user


@router.patch("/auth/me")
def rename(body: NameIn, user=Depends(require_user)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="NAME_REQUIRED")
    with connect() as conn:
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user["id"]))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return public_user(row)


@router.get("/users")
def users(user=Depends(require_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT users.*, (SELECT COUNT(*) FROM datasets WHERE datasets.owner_id = users.id) AS runs
            FROM users ORDER BY users.id
            """
        ).fetchall()
    return [
        {**public_user(row), "runs": row["runs"]}
        for row in rows
    ]


@router.delete("/users/{user_id}")
def delete_user(user_id: int, user=Depends(require_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="CANNOT_DELETE_SELF")
    from records import delete_dataset
    with connect() as conn:
        rows = conn.execute("SELECT id FROM datasets WHERE owner_id = ?", (user_id,)).fetchall()
    for row in rows:
        delete_dataset(row["id"])
    with connect() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return {"ok": True}
