"""改之前的提醒、改完后的回答。先用规则写事实；有密钥才请模型改写。"""

import json
import os
import urllib.request

from cleaning import to_number, trim_ws


PRIORITY = ("amount", "iddup", "outlier", "duplicate", "spelling", "date", "phone", "email", "space", "missing")

LABELS = {
    "zh": {
        "missing": "空值", "duplicate": "整行重复", "date": "日期不统一", "outlier": "数字离群",
        "space": "首尾空格", "spelling": "写法不一致", "iddup": "编号重复", "amount": "金额对不上",
        "phone": "电话格式", "email": "邮箱格式",
    },
    "en": {
        "missing": "missing", "duplicate": "duplicate rows", "date": "dates", "outlier": "outliers",
        "space": "extra spaces", "spelling": "spellings", "iddup": "repeated ids", "amount": "amount mismatches",
        "phone": "phones", "email": "emails",
    },
}


def _lines_for(issues, lang, limit=6):
    ordered = sorted(issues, key=lambda issue: PRIORITY.index(issue["type"]) if issue["type"] in PRIORITY else 99)
    chosen = []
    seen = set()
    for issue in ordered:
        if issue["type"] in seen and issue["type"] in {"missing", "space", "phone"}:
            continue
        seen.add(issue["type"])
        chosen.append(issue)
        if len(chosen) >= limit:
            break
    return chosen


def rule_plan(question, result_view, lang):
    labels = LABELS["zh" if lang == "zh" else "en"]
    issues = result_view["issues"]
    counts = result_view["by_type"]
    present = [f"{labels[key]} {counts.get(key, 0)}" for key in PRIORITY if counts.get(key, 0)]
    focus = _lines_for(issues, lang)
    if lang == "zh":
        head = f"你要回答的问题是：「{question}」。" if question else "你还没有写要回答的问题。可以先写一句，例如「华北的椅子卖了多少」。"
        body = [head, "", f"这张表有 {result_view['row_count']} 行、{result_view['col_count']} 列，检出 {len(issues)} 个问题：" + ("、".join(present) if present else "没有")]
        if focus:
            body.append("")
            body.append("动手改之前，建议先看这些：")
            for issue in focus:
                body.append(f"- {issue['explanation']}")
        body.append("")
        body.append("系统不会自动改表。金额对不上时，不要直接接受「改成中位数」。编号重复只是提醒，接受表示你看过并决定保留。")
        return "\n".join(body)
    head = f'Your question: "{question}".' if question else "You have not written a question yet."
    body = [head, "", f"{result_view['row_count']} rows, {result_view['col_count']} columns, {len(issues)} issues: " + (", ".join(present) if present else "none")]
    if focus:
        body.append("")
        body.append("Look at these before you accept anything:")
        for issue in focus:
            body.append(f"- {issue['explanation']}")
    body.append("")
    body.append("Nothing is changed until you decide. Do not accept a median for an amount that fails the quantity × price check.")
    return "\n".join(body)


def _region_totals(headers, rows, columns):
    region_i = columns.get("region")
    amount_i = columns.get("amount")
    if region_i is None or amount_i is None:
        return []
    if region_i >= len(headers) or amount_i >= len(headers):
        return []
    totals = {}
    order = []
    for row in rows:
        name = trim_ws(row[region_i] if region_i < len(row) else "") or "(空)"
        number = to_number(row[amount_i] if amount_i < len(row) else "")
        if number is None:
            continue
        if name not in totals:
            order.append(name)
        totals[name] = totals.get(name, 0) + number
    return [(name, totals[name]) for name in order]


def rule_answer(question, result_view, cleaned, lang):
    ignored = [issue for issue in result_view["issues"] if result_view["decisions"].get(issue["key"], {}).get("action") == "ignore"]
    totals = _region_totals(cleaned["headers"], cleaned["rows"], result_view["columns"])
    if lang == "zh":
        lines = []
        lines.append(f"问题：「{question}」。" if question else "你没有填写具体问题，下面只是这次清洗的结果。")
        lines.append(
            f"按你的决定，干净表有 {len(cleaned['rows'])} 行（去掉完全相同的行 {cleaned['duplicates_removed']} 行）。"
            f"你改或确认了 {cleaned['fixed']} 条，忽略了 {cleaned['ignored']} 条。"
        )
        if ignored:
            lines.append("")
            lines.append("你选择不改的有：")
            for issue in ignored[:8]:
                lines.append(f"- {issue['explanation']}")
        if totals:
            lines.append("")
            lines.append("按地区把能识别的金额相加（这是规则算的，不是模型猜的）：")
            for name, total in totals:
                lines.append(f"- {name}：{round(total, 2)}")
        if question:
            lines.append("")
            lines.append("如果上面的地区合计还回答不了你的原话，是因为有的格子你选择了保留原值，或者地区写法还没统一。")
        return "\n".join(lines)
    lines = []
    lines.append(f'Question: "{question}".' if question else "No question was entered. This is only the cleaning result.")
    lines.append(
        f"The cleaned table has {len(cleaned['rows'])} rows "
        f"({cleaned['duplicates_removed']} exact duplicate rows removed). "
        f"Confirmed or edited: {cleaned['fixed']}. Ignored: {cleaned['ignored']}."
    )
    if ignored:
        lines.append("")
        lines.append("Left unchanged:")
        for issue in ignored[:8]:
            lines.append(f"- {issue['explanation']}")
    if totals:
        lines.append("")
        lines.append("Amount summed by region from the cleaned rows:")
        for name, total in totals:
            lines.append(f"- {name}: {round(total, 2)}")
    return "\n".join(lines)


def rewrite(text, lang):
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key or not text:
        return None
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    language = "中文" if lang == "zh" else "English"
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是数据清洗助手。只能转述用户给出的事实，不能编造数字，不能声称已经改了表格。"
                    f"用{language}写成给同事看的短说明，不超过 220 字，不要用标题。"
                ),
            },
            {"role": "user", "content": text},
        ],
    }
    request = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"].strip()
        return content or None
    except Exception:
        return None
