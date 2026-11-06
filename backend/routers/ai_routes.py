"""清洗完成之后的提问。只有这一步和模板分析会扣次数。"""

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from database import connect
from llm_client import chat_text, configured
from quota import assert_available, record, summary
from records import build_cleaned, decisions_map, fetch_dataset, issues_for, now, owned, read_grid
from schemas import QuestionIn

router = APIRouter(prefix="/api")


@router.get("/usage")
def usage(user=Depends(require_user)):
    return summary(user["id"])


def _facts(dataset_id, lang):
    row = fetch_dataset(dataset_id)
    headers, rows = read_grid(dataset_id)
    issues = issues_for(dataset_id)
    decisions = decisions_map(issues)
    cleaned = build_cleaned(headers, rows, issues, decisions)
    en = lang == "en"
    ignored = [issue for issue in issues if decisions.get(issue["key"], {}).get("action") == "ignore"]
    edited = [issue for issue in issues if decisions.get(issue["key"], {}).get("action") == "edit"]
    auto = [issue for issue in issues if issue.get("auto") and decisions.get(issue["key"], {}).get("action") == "accept"]
    if en:
        lines = [
            f"Dataset: {row['name']}. Template: {row['template_name'] or 'none'}.",
            f"Original table: {row['row_count']} rows, {row['col_count']} columns. Columns: {', '.join(headers)}.",
            f"Cleaned table: {len(cleaned['rows'])} rows. Exact duplicate rows removed: {cleaned['duplicates_removed']}.",
            f"Low-risk fixes already applied: {len(auto)}. Edited by the reviewer: {len(edited)}. Left unchanged: {len(ignored)}.",
        ]
    else:
        lines = [
            f"表名：{row['name']}。模板：{row['template_name'] or '无'}。",
            f"原始表 {row['row_count']} 行、{row['col_count']} 列。列名：{'、'.join(headers)}。",
            f"清洗后还剩 {len(cleaned['rows'])} 行。删掉的完全重复行：{cleaned['duplicates_removed']}。",
            f"已自动改掉的低风险问题：{len(auto)} 条。复核人改写：{len(edited)} 条。决定不改：{len(ignored)} 条。",
        ]
    for issue in ignored:
        suggestion = issue["suggestion"].get("value") or ""
        if en:
            lines.append(f"Unchanged row {issue['row'] + 1} {issue['field']}: still '{issue['original']}'. Suggested '{suggestion}'.")
        else:
            lines.append(f"未改：第 {issue['row'] + 1} 行 {issue['field']} 仍是「{issue['original']}」，建议曾是「{suggestion}」。")
    for issue in (edited + auto)[:12]:
        suggestion = issue["editedValue"] or issue["suggestion"].get("value") or ""
        if en:
            lines.append(f"Changed row {issue['row'] + 1} {issue['field']}: '{issue['original']}' -> '{suggestion}'.")
        else:
            lines.append(f"已改：第 {issue['row'] + 1} 行 {issue['field']} 「{issue['original']}」改成「{suggestion}」。")
    lines.append("Cleaned rows:" if en else "清洗后的前 8 行：")
    for cells in cleaned["rows"][:8]:
        lines.append(" | ".join(cells))
    return "\n".join(lines)


@router.post("/ai/ask")
def ask(body: QuestionIn, dataset_id: int, user=Depends(require_user)):
    row = fetch_dataset(dataset_id)
    if not row or not owned(user, row):
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if row["status"] != "done":
        raise HTTPException(status_code=400, detail="NOT_DONE")
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="QUESTION_REQUIRED")
    lang = "en" if body.lang == "en" else "zh"
    facts = _facts(dataset_id, lang)
    source = "rules"
    if lang == "en":
        answer = f"No model key is configured. These are the cleaned-table facts, not a model answer.\n\n{facts}"
        system = (
            "You help a colleague decide what from this cleaned spreadsheet can go into a report. "
            "Use the row numbers, column names and values in the material. "
            "Do not say the material is insufficient and then stop. "
            "Start with which columns are safe to report and which few cells should be left out. "
            "If a cell is marked unchanged, say that cell is not final. "
            "Do not claim you edited the sheet. Do not apologize. 90 to 140 words."
        )
    else:
        answer = f"还没有配置模型密钥。下面是清洗后的事实，不是模型回答。\n\n{facts}"
        system = (
            "你是业务同事，帮着看这张已经洗过的表，哪些能拿去汇报。"
            "用材料里的行号、列名和原值回答，不要说材料不足然后停下。"
            "先说哪些列可以直接用，再点出先不要写进汇报的那几格。"
            "标成未改的格子，要明确说还不能当最终数。"
            "不要声称你又改了表，也不要道歉。180到260字。"
        )
    if configured():
        try:
            assert_available(user["id"])
        except ValueError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        result = chat_text([
            {"role": "system", "content": system},
            {"role": "user", "content": (f"Question: {question}\n\nMaterial:\n{facts}" if lang == "en" else f"问题：{question}\n\n材料：\n{facts}")},
        ])
        if result and result["content"]:
            record(user["id"], "ask", result["prompt_tokens"], result["completion_tokens"])
            answer = result["content"]
            source = "llm"
        else:
            answer = (f"The model returned nothing. Facts from the cleaned table:\n\n{facts}" if lang == "en" else f"模型没有返回。下面仍是清洗后的事实。\n\n{facts}")
    with connect() as conn:
        conn.execute(
            "INSERT INTO ai_asks (user_id, dataset_id, question, answer, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user["id"], dataset_id, question, answer, source, now()),
        )
    return {"question": question, "answer": answer, "source": source, "usage": summary(user["id"])}


@router.get("/ai/asks")
def history(dataset_id: int, user=Depends(require_user)):
    row = fetch_dataset(dataset_id)
    if not row or not owned(user, row):
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    with connect() as conn:
        rows = conn.execute(
            "SELECT question, answer, source, created_at FROM ai_asks WHERE dataset_id = ? AND user_id = ? ORDER BY id DESC",
            (dataset_id, user["id"]),
        ).fetchall()
    return [dict(item) for item in rows]
