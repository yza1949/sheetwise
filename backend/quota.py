"""每人 30 次模型调用，另加 10 万 token 总闸。清洗本身不扣次数。"""

from datetime import datetime

from database import connect
from llm_client import configured

CALL_LIMIT = 30
TOKEN_LIMIT = 100_000


def summary(user_id):
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS calls,
                   COALESCE(SUM(prompt_tokens + completion_tokens), 0) AS tokens
            FROM usage_events WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    used_calls = int(row["calls"] or 0)
    used_tokens = int(row["tokens"] or 0)
    return {
        "usedCalls": used_calls,
        "callLimit": CALL_LIMIT,
        "remainingCalls": max(0, CALL_LIMIT - used_calls),
        "usedTokens": used_tokens,
        "tokenLimit": TOKEN_LIMIT,
        "remainingTokens": max(0, TOKEN_LIMIT - used_tokens),
        "keyConfigured": configured(),
    }


def assert_available(user_id):
    current = summary(user_id)
    if current["remainingCalls"] <= 0 or current["remainingTokens"] <= 0:
        raise ValueError("QUOTA")
    return current


def record(user_id, kind, prompt_tokens, completion_tokens):
    created = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO usage_events (user_id, kind, prompt_tokens, completion_tokens, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, kind, int(prompt_tokens or 0), int(completion_tokens or 0), created),
        )
