"""上传、列表、复核决定、完成、下载。"""

import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from auth import require_user
from database import connect, loads
from demo_tables import pack
from records import (
    accept_all,
    create_dataset,
    dataset_detail,
    delete_dataset,
    fetch_dataset,
    list_datasets,
    owned,
    report_payload,
    set_decision,
    undo_decision,
    write_answer,
    write_plan,
)
from schemas import DecisionIn, LangIn, QuestionIn, RulesIn

router = APIRouter(prefix="/api/datasets")


def _lang(value):
    return "en" if value == "en" else "zh"


def _open(user, dataset_id):
    row = fetch_dataset(dataset_id)
    if not row or not owned(user, row):
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return row


@router.get("")
def listing(q: str = "", status: str = "all", user=Depends(require_user)):
    return list_datasets(user, q.strip(), status)


@router.post("")
async def upload(
    file: UploadFile = File(...),
    name: str = Form(""),
    question: str = Form(""),
    lang: str = Form("zh"),
    template_name: str = Form(""),
    rules: str = Form("[]"),
    user=Depends(require_user),
):
    payload = await file.read()
    try:
        parsed_rules = json.loads(rules or "[]")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="BAD_RULES") from exc
    try:
        dataset_id = create_dataset(user, file.filename or "upload.csv", payload, name, question, _lang(lang), template_name, parsed_rules)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return dataset_detail(dataset_id, _lang(lang))


@router.post("/sample")
def sample(body: QuestionIn, user=Depends(require_user)):
    language = _lang(body.lang)
    item = pack("sales", language)
    try:
        dataset_id = create_dataset(
            user, "sales_dirty.csv", item["dirty"].encode("utf-8"), item["name"],
            body.question, language, item["name"], item["rules"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return dataset_detail(dataset_id, language)


def _rules_fit(rules, headers):
    names = set(headers)
    for rule in rules or []:
        for key in ("field", "qty", "price"):
            value = (rule or {}).get(key) if isinstance(rule, dict) else None
            if value and value not in names:
                return False
    return True


@router.post("/sample/{slug}")
def sample_slug(slug: str, body: RulesIn, user=Depends(require_user)):
    language = _lang(body.lang)
    item = pack(slug, language)
    if not item:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    chosen = body.rules if body.rules and _rules_fit(body.rules, item["headers"]) else item["rules"]
    try:
        dataset_id = create_dataset(
            user, f"{slug}_dirty.csv", item["dirty"].encode("utf-8"), item["name"],
            "", language, item["name"], chosen,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return dataset_detail(dataset_id, language)


@router.get("/{dataset_id}")
def detail(dataset_id: int, lang: str = "zh", user=Depends(require_user)):
    _open(user, dataset_id)
    return dataset_detail(dataset_id, _lang(lang))


@router.delete("/{dataset_id}")
def remove(dataset_id: int, user=Depends(require_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    _open(user, dataset_id)
    delete_dataset(dataset_id)
    return {"ok": True}


@router.post("/{dataset_id}/plan")
def plan(dataset_id: int, body: QuestionIn, user=Depends(require_user)):
    _open(user, dataset_id)
    write_plan(dataset_id, body.question.strip(), _lang(body.lang))
    return dataset_detail(dataset_id, _lang(body.lang))


@router.post("/{dataset_id}/complete")
def complete(dataset_id: int, body: LangIn, user=Depends(require_user)):
    _open(user, dataset_id)
    try:
        write_answer(dataset_id, _lang(body.lang))
    except ValueError as exc:
        code = str(exc)
        status = 400 if code in {"UNREVIEWED", "CLOSED"} else 400
        raise HTTPException(status_code=status, detail=code) from exc
    return dataset_detail(dataset_id, _lang(body.lang))


@router.post("/{dataset_id}/anomalies/{anomaly_id}")
def decide(dataset_id: int, anomaly_id: int, body: DecisionIn, user=Depends(require_user)):
    _open(user, dataset_id)
    try:
        set_decision(user, dataset_id, anomaly_id, body.action, body.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return dataset_detail(dataset_id, "zh")


@router.post("/{dataset_id}/anomalies/{anomaly_id}/undo")
def undo(dataset_id: int, anomaly_id: int, user=Depends(require_user)):
    _open(user, dataset_id)
    try:
        undo_decision(dataset_id, anomaly_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/{dataset_id}/accept-all")
def accept_remaining(dataset_id: int, user=Depends(require_user)):
    _open(user, dataset_id)
    try:
        accept_all(dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/{dataset_id}/download")
def download(dataset_id: int, user=Depends(require_user)):
    row = _open(user, dataset_id)
    if row["status"] != "done":
        raise HTTPException(status_code=400, detail="NOT_DONE")
    _report, csv_text = report_payload(dataset_id)
    filename = quote(f"{row['name']}_cleaned.csv")
    return Response(
        content=csv_text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"cleaned.csv\"; filename*=UTF-8''{filename}"},
    )


@router.get("/{dataset_id}/report")
def report_json(dataset_id: int, user=Depends(require_user)):
    row = _open(user, dataset_id)
    if row["status"] != "done":
        raise HTTPException(status_code=400, detail="NOT_DONE")
    report, _csv_text = report_payload(dataset_id)
    return report
