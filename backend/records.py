"""把一次分析读写进 SQLite。不管网页长什么样。"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from cleaning import (
    analyze,
    apply_learned,
    apply_template_rules,
    build_cleaned,
    explain,
    is_safe_auto,
    merge_issues,
    normalize_rules,
    parse_upload,
    quality_score,
    to_csv,
)
from database import connect, data_dir, dumps, loads
from narrate import rewrite, rule_answer, rule_plan

SAMPLE = Path(__file__).resolve().parent / "sample" / "sales_demo.csv"
MAX_BYTES = 2 * 1024 * 1024


def now():
    return datetime.utcnow().isoformat(timespec="seconds")


def load_rules(user_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT rule_key, suggestion_json FROM learned_rules WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {row["rule_key"]: loads(row["suggestion_json"], {}) for row in rows}


def save_rule(user_id, issue):
    key = f"{issue['type']}|{issue['field']}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO learned_rules (user_id, rule_key, suggestion_json)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, rule_key) DO UPDATE SET suggestion_json = excluded.suggestion_json
            """,
            (user_id, key, dumps(issue["suggestion"])),
        )


def grid_paths(dataset_id):
    folder = data_dir() / "uploads" / str(dataset_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "original.bin", folder / "grid.json"


def read_grid(dataset_id):
    _original, grid = grid_paths(dataset_id)
    payload = json.loads(grid.read_text(encoding="utf-8"))
    return payload["headers"], payload["rows"]


def fetch_dataset(dataset_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    return row


def owned(user, dataset):
    return bool(dataset) and (user["role"] == "admin" or dataset["owner_id"] == user["id"])


def issues_for(dataset_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM anomalies WHERE dataset_id = ? ORDER BY row_index, col_index, id",
            (dataset_id,),
        ).fetchall()
    issues = []
    for row in rows:
        issues.append({
            "id": row["id"],
            "key": row["issue_key"],
            "type": row["type"],
            "row": row["row_index"],
            "col": row["col_index"],
            "field": row["field"],
            "original": row["original"],
            "suggestion": loads(row["suggestion_json"], {}),
            "learned": bool(row["learned"]),
            "auto": bool(row["auto_fixed"]) if "auto_fixed" in row.keys() else False,
            "decision": row["decision"],
            "editedValue": row["edited_value"],
        })
    return issues


def decisions_map(issues):
    decisions = {}
    for issue in issues:
        if issue["decision"]:
            decisions[issue["key"]] = {"action": issue["decision"], "value": issue["editedValue"]}
    return decisions


def decorate(issues, lang):
    copied = []
    for issue in issues:
        item = dict(issue)
        item["explanation"] = explain(issue, "zh" if lang == "zh" else "en")
        copied.append(item)
    return copied


def dataset_dict(row, user_name, issues):
    stats = loads(row["stats_json"], {})
    plan = loads(row["plan_json"], {})
    answer = loads(row["answer_json"], {})
    decided = sum(1 for issue in issues if issue["decision"])
    return {
        "id": row["id"],
        "name": row["name"],
        "fileName": row["file_name"],
        "fileSize": row["file_size"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "ownerId": row["owner_id"],
        "ownerName": user_name,
        "rowCount": row["row_count"],
        "colCount": row["col_count"],
        "truncated": bool(row["truncated"]),
        "question": row["question"],
        "templateName": row["template_name"] if "template_name" in row.keys() else "",
        "rules": loads(row["rules_json"], []) if "rules_json" in row.keys() else [],
        "log": loads(row["log_json"], []) if "log_json" in row.keys() else [],
        "engine": "规则引擎",
        "plan": plan,
        "answer": answer,
        "byType": stats.get("byType") or {},
        "issueCount": len(issues),
        "decidedCount": decided,
    }


def dataset_detail(dataset_id, lang):
    row = fetch_dataset(dataset_id)
    if not row:
        return None
    with connect() as conn:
        owner = conn.execute("SELECT name FROM users WHERE id = ?", (row["owner_id"],)).fetchone()
    issues = decorate(issues_for(dataset_id), lang)
    headers, rows = read_grid(dataset_id)
    detail = dataset_dict(row, owner["name"] if owner else "", issues)
    detail["headers"] = headers
    detail["preview"] = rows[:6]
    detail["issues"] = issues
    issue_rows = {issue["row"] for issue in issues}
    detail["cleanRows"] = [
        {"row": index + 1, "cells": row}
        for index, row in enumerate(rows)
        if index not in issue_rows
    ]
    stored_log = loads(row["log_json"], []) if "log_json" in row.keys() else []
    if isinstance(stored_log, dict):
        detail["log"] = stored_log.get(lang) or stored_log.get("zh") or []
    return detail


def create_dataset(user, filename, payload, name, question, lang, template_name="", rules=None):
    if len(payload) > MAX_BYTES:
        raise ValueError("TOO_BIG")
    if not filename:
        raise ValueError("BAD_TYPE")
    try:
        headers, rows, truncated = parse_upload(filename, payload)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("BAD_FILE") from exc
    if not headers:
        raise ValueError("EMPTY")
    confirmed = normalize_rules(rules or [])
    result = analyze(headers, rows)
    result["issues"] = apply_learned(result["issues"], load_rules(user["id"]))
    result["issues"] = merge_issues(result["issues"], apply_template_rules(headers, rows, confirmed))
    for issue in result["issues"]:
        issue["auto"] = is_safe_auto(issue)
    by_type = {}
    for issue in result["issues"]:
        by_type[issue["type"]] = by_type.get(issue["type"], 0) + 1
    labels_zh = {
        "missing": "空值", "duplicate": "整行重复", "date": "日期", "outlier": "离群",
        "space": "空格", "spelling": "写法", "iddup": "编号重复", "amount": "金额",
        "phone": "电话", "email": "邮箱", "enum": "不在模板里", "range": "超出范围",
    }
    labels_en = {
        "missing": "empty", "duplicate": "duplicate row", "date": "date", "outlier": "outlier",
        "space": "spaces", "spelling": "spelling", "iddup": "id duplicate", "amount": "amount",
        "phone": "phone", "email": "email", "enum": "not in template", "range": "out of range",
    }
    present_zh = "、".join(f"{labels_zh.get(key, key)} {value}" for key, value in by_type.items() if value)
    present_en = ", ".join(f"{labels_en.get(key, key)} {value}" for key, value in by_type.items() if value)
    auto_count = sum(1 for issue in result["issues"] if issue["auto"])
    pending = len(result["issues"]) - auto_count
    log = {
        "zh": [
            {"text": f"解析完成：{len(rows)} 行 × {len(headers)} 列"},
            {"text": f"检测到 {len(result['issues'])} 处异常" + (f"：{present_zh}" if present_zh else "")},
            {"text": f"已套用模板「{template_name}」，规则 {len(confirmed)} 条" if template_name else "未使用模板，只跑通用规则"},
            {"text": f"已自动接受 {auto_count} 条低风险修改，还需你看 {pending} 条"},
            {"text": "分析完成，等待人工复核"},
        ],
        "en": [
            {"text": f"Parsed {len(rows)} rows × {len(headers)} columns"},
            {"text": f"Found {len(result['issues'])} issues" + (f": {present_en}" if present_en else "")},
            {"text": f"Applied template “{template_name}”, {len(confirmed)} rules" if template_name else "No template, general checks only"},
            {"text": f"Auto-accepted {auto_count} low-risk fixes. {pending} still need you."},
            {"text": "Ready for review"},
        ],
    }
    stats = {
        "byType": by_type,
        "columnTypes": result["column_types"],
        "columns": result["columns"],
        "truncated": truncated,
    }
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO datasets (
              owner_id, name, file_name, file_size, status, created_at,
              row_count, col_count, truncated, question, stats_json, template_name, rules_json, log_json
            ) VALUES (?, ?, ?, ?, 'review', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                (name or filename).strip()[:120] or filename,
                filename,
                len(payload),
                now(),
                len(rows),
                len(headers),
                1 if truncated else 0,
                (question or "").strip(),
                dumps(stats),
                template_name or "",
                dumps(confirmed),
                dumps(log),
            ),
        )
        dataset_id = cursor.lastrowid
        original, grid = grid_paths(dataset_id)
        original.write_bytes(payload)
        grid.write_text(dumps({"headers": headers, "rows": rows}), encoding="utf-8")
        if result["issues"]:
            conn.executemany(
                """
                INSERT INTO anomalies (
                  dataset_id, issue_key, type, row_index, col_index, field, original, suggestion_json, learned, decision, auto_fixed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        dataset_id, issue["key"], issue["type"], issue["row"], issue["col"], issue["field"],
                        issue["original"], dumps(issue["suggestion"]), 1 if issue["learned"] else 0,
                        "accept" if issue.get("auto") else None, 1 if issue.get("auto") else 0,
                    )
                    for issue in result["issues"]
                ],
            )
    return dataset_id


def write_plan(dataset_id, question, lang):
    lang = "en" if lang == "en" else "zh"
    row = fetch_dataset(dataset_id)
    stats = loads(row["stats_json"], {})
    issues = decorate(issues_for(dataset_id), lang)
    view = {
        "issues": issues,
        "by_type": stats.get("byType") or {},
        "row_count": row["row_count"],
        "col_count": row["col_count"],
        "columns": stats.get("columns") or {},
        "decisions": decisions_map(issues_for(dataset_id)),
    }
    text = rule_plan(question, view, lang)
    source = "rules"
    rewritten = rewrite(text, lang)
    if rewritten:
        text = rewritten
        source = "llm"
    plan = loads(row["plan_json"], {})
    plan[lang] = {"text": text, "source": source}
    with connect() as conn:
        conn.execute(
            "UPDATE datasets SET question = ?, plan_json = ? WHERE id = ?",
            (question, dumps(plan), dataset_id),
        )
    return plan[lang]


def write_answer(dataset_id, lang):
    lang = "en" if lang == "en" else "zh"
    row = fetch_dataset(dataset_id)
    headers, rows = read_grid(dataset_id)
    raw_issues = issues_for(dataset_id)
    decisions = decisions_map(raw_issues)
    if any(not issue["decision"] for issue in raw_issues):
        raise ValueError("UNREVIEWED")
    cleaned = build_cleaned(headers, rows, raw_issues, decisions)
    score = quality_score(row["row_count"], row["col_count"], raw_issues, decisions)
    stats = loads(row["stats_json"], {})
    view = {
        "issues": decorate(raw_issues, lang),
        "by_type": stats.get("byType") or {},
        "row_count": row["row_count"],
        "col_count": row["col_count"],
        "columns": stats.get("columns") or {},
        "decisions": decisions,
    }
    text = rule_answer(row["question"], view, cleaned, lang)
    source = "rules"
    answer = loads(row["answer_json"], {})
    answer[lang] = {"text": text, "source": source}
    created = now()
    with connect() as conn:
        conn.execute(
            "UPDATE datasets SET status = 'done', answer_json = ? WHERE id = ?",
            (dumps(answer), dataset_id),
        )
        conn.execute(
            """
            INSERT INTO reports (
              dataset_id, created_at, issues_found, fixed, ignored, duplicates_removed, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id) DO UPDATE SET
              created_at = excluded.created_at,
              issues_found = excluded.issues_found,
              fixed = excluded.fixed,
              ignored = excluded.ignored,
              duplicates_removed = excluded.duplicates_removed,
              quality_score = excluded.quality_score
            """,
            (
                dataset_id, created, len(raw_issues), cleaned["fixed"], cleaned["ignored"],
                cleaned["duplicates_removed"], score,
            ),
        )
    return answer[lang], cleaned, score


def report_payload(dataset_id):
    row = fetch_dataset(dataset_id)
    headers, rows = read_grid(dataset_id)
    raw_issues = issues_for(dataset_id)
    decisions = decisions_map(raw_issues)
    cleaned = build_cleaned(headers, rows, raw_issues, decisions)
    score = quality_score(row["row_count"], row["col_count"], raw_issues, decisions)
    stats = loads(row["stats_json"], {})
    return {
        "name": row["name"],
        "fileName": row["file_name"],
        "createdAt": row["created_at"],
        "rows": row["row_count"],
        "columns": row["col_count"],
        "issuesFound": len(raw_issues),
        "fixed": cleaned["fixed"],
        "ignored": cleaned["ignored"],
        "duplicatesRemoved": cleaned["duplicates_removed"],
        "qualityScore": score,
        "byType": stats.get("byType") or {},
        "question": row["question"],
        "answer": loads(row["answer_json"], {}),
        "decisions": [
            {
                "type": issue["type"],
                "row": issue["row"] + 1,
                "field": None if issue["col"] < 0 else issue["field"],
                "original": issue["original"],
                "suggestion": issue["suggestion"].get("value"),
                "decision": issue["decision"] or "none",
                "editedValue": issue["editedValue"],
                "learned": issue["learned"],
            }
            for issue in raw_issues
        ],
    }, to_csv(cleaned["headers"], cleaned["rows"])


def set_decision(user, dataset_id, anomaly_id, action, value):
    if action not in {"accept", "edit", "ignore"}:
        raise ValueError("BAD_ACTION")
    row = fetch_dataset(dataset_id)
    if not row or row["status"] == "done":
        raise ValueError("CLOSED")
    with connect() as conn:
        anomaly = conn.execute(
            "SELECT * FROM anomalies WHERE id = ? AND dataset_id = ?",
            (anomaly_id, dataset_id),
        ).fetchone()
    if not anomaly:
        raise ValueError("NOT_FOUND")
    issue = {
        "type": anomaly["type"],
        "field": anomaly["field"],
        "suggestion": loads(anomaly["suggestion_json"], {}),
    }
    edited = None
    if action == "edit":
        edited = "" if value is None else str(value)
        issue["suggestion"] = {"kind": "custom", "value": edited, "detail": edited}
    elif action == "accept":
        issue["suggestion"] = loads(anomaly["suggestion_json"], {})
    with connect() as conn:
        conn.execute(
            "UPDATE anomalies SET decision = ?, edited_value = ? WHERE id = ?",
            (action, edited, anomaly_id),
        )
    if action in {"accept", "edit"} and anomaly["type"] not in {"duplicate", "iddup"}:
        save_rule(user["id"], issue)
    return True


def undo_decision(dataset_id, anomaly_id):
    row = fetch_dataset(dataset_id)
    if not row or row["status"] == "done":
        raise ValueError("CLOSED")
    with connect() as conn:
        conn.execute(
            "UPDATE anomalies SET decision = NULL, edited_value = NULL, auto_fixed = 0 WHERE id = ? AND dataset_id = ?",
            (anomaly_id, dataset_id),
        )


def accept_all(dataset_id):
    row = fetch_dataset(dataset_id)
    if not row or row["status"] == "done":
        raise ValueError("CLOSED")
    with connect() as conn:
        conn.execute(
            """
            UPDATE anomalies SET decision = 'accept'
            WHERE dataset_id = ? AND decision IS NULL
            """,
            (dataset_id,),
        )


def delete_dataset(dataset_id):
    folder = data_dir() / "uploads" / str(dataset_id)
    if folder.exists():
        shutil.rmtree(folder)
    with connect() as conn:
        conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))


def list_datasets(user, query, status):
    sql = """
      SELECT datasets.*, users.name AS owner_name,
        (SELECT COUNT(*) FROM anomalies WHERE anomalies.dataset_id = datasets.id) AS issue_count,
        (SELECT COUNT(*) FROM anomalies WHERE anomalies.dataset_id = datasets.id AND decision IS NOT NULL) AS decided_count
      FROM datasets JOIN users ON users.id = datasets.owner_id
      WHERE 1 = 1
    """
    params = []
    if user["role"] != "admin":
        sql += " AND datasets.owner_id = ?"
        params.append(user["id"])
    if status and status != "all":
        sql += " AND datasets.status = ?"
        params.append(status)
    if query:
        sql += " AND lower(datasets.name) LIKE ?"
        params.append(f"%{query.lower()}%")
    sql += " ORDER BY datasets.id DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    items = []
    for row in rows:
        item = dataset_dict(row, row["owner_name"], [])
        item["issueCount"] = row["issue_count"]
        item["decidedCount"] = row["decided_count"]
        items.append(item)
    return items
