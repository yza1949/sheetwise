"""模板列表，以及用 DeepSeek 或内置规则读出要执行的规则。"""

import csv
import io
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from auth import require_user
from cleaning import guess_rules, normalize_rules, parse_upload, rules_from_model_text
from database import connect, loads
from demo_tables import pack
from llm_client import chat, configured
from quota import assert_available, record

router = APIRouter(prefix="/api/templates")


def _lang(value):
    return "en" if value == "en" else "zh"


def public_template(row, lang="zh"):
    item = pack(row["slug"], lang) if row["slug"] else None
    if item:
        return {
            "id": row["id"],
            "slug": row["slug"],
            "name": item["name"],
            "summary": item["summary"],
            "note": item["note"],
            "headers": item["headers"],
            "sample": item["sample"],
            "rules": item["rules"],
            "builtin": True,
        }
    return {
        "id": row["id"],
        "slug": row["slug"],
        "name": row["name"],
        "summary": row["summary"],
        "note": row["note"],
        "headers": loads(row["headers_json"], []),
        "sample": loads(row["sample_json"], []),
        "rules": loads(row["rules_json"], []),
        "builtin": bool(row["builtin"]),
    }


def _prompt(headers, sample, note):
    return [
        {
            "role": "system",
            "content": (
                "你只输出 JSON。根据模板示例和说明，列出可执行的校验规则。"
                "type 只能是 not_empty、unique、enum、date、phone、email、equals_product、number_range、non_negative、positive。"
                "field、qty、price 必须是给定表头里的原文。不要编造表里没有的列。"
                '格式 {"rules":[{"type":"enum","field":"地区","text":"一句中文","values":["North"],"qty":"","price":"","min":null,"max":null}]}'
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"headers": headers, "sample": sample[:8], "note": note[:1000]}, ensure_ascii=False),
        },
    ]


@router.get("")
def listing(lang: str = "zh", user=Depends(require_user)):
    language = _lang(lang)
    with connect() as conn:
        rows = conn.execute("SELECT * FROM templates ORDER BY id").fetchall()
    return [public_template(row, language) for row in rows]


@router.get("/{slug}")
def one(slug: str, lang: str = "zh", user=Depends(require_user)):
    with connect() as conn:
        row = conn.execute("SELECT * FROM templates WHERE slug = ?", (slug,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    shown = public_template(row, _lang(lang))
    item = pack(row["slug"], _lang(lang))
    if item:
        parsed = list(csv.reader(io.StringIO(item["dirty"])))
        shown["demo"] = parsed[1:]
    return shown


@router.post("/{slug}/analyze")
def analyze_builtin(slug: str, lang: str = "zh", user=Depends(require_user)):
    language = _lang(lang)
    with connect() as conn:
        row = conn.execute("SELECT * FROM templates WHERE slug = ?", (slug,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    shown = public_template(row, language)
    authored = shown["rules"]
    source = "builtin"
    rules = authored
    if configured():
        try:
            assert_available(user["id"])
        except ValueError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        result = chat(_prompt(shown["headers"], shown["sample"], shown["note"]))
        if result:
            parsed = rules_from_model_text(result["content"], shown["headers"])
            record(user["id"], "template", result["prompt_tokens"], result["completion_tokens"])
            if parsed:
                rules = parsed
                source = "llm"
    return {"rules": normalize_rules(rules), "source": source, "template": shown}


@router.post("/analyze")
async def analyze_upload(
    note: str = Form(""),
    file: UploadFile = File(...),
    user=Depends(require_user),
):
    payload = await file.read()
    if len(payload) > 256 * 1024:
        raise HTTPException(status_code=400, detail="TOO_BIG")
    try:
        headers, rows, _truncated = parse_upload(file.filename or "template.csv", payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not headers:
        raise HTTPException(status_code=400, detail="EMPTY")
    sample = rows[:8]
    source = "rules"
    rules = guess_rules(headers, sample, note)
    if configured():
        try:
            assert_available(user["id"])
        except ValueError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        result = chat(_prompt(headers, sample, note))
        if result:
            parsed = rules_from_model_text(result["content"], headers)
            record(user["id"], "template", result["prompt_tokens"], result["completion_tokens"])
            if parsed:
                rules = parsed
                source = "llm"
            else:
                source = "rules"
    return {"rules": rules, "source": source, "headers": headers, "sample": sample, "note": note}
