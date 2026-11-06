"""检测和修复。纯函数：不读数据库，不处理 HTTP。"""

import csv
import io
import re
from datetime import datetime

ROW_CAP = 1500
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

QTY_KEYS = ("units", "quantity", "qty", "数量")
PRICE_KEYS = ("unit price", "unit_price", "单价")
AMOUNT_KEYS = ("amount", "total", "金额", "总价", "销售额")
REGION_KEYS = ("region", "地区", "区域")
ID_KEYS = ("order id", "order_id", "orderid", "订单号", "订单编号", "单号")
PHONE_KEYS = ("phone", "mobile", "tel", "电话", "手机", "手机号")
EMAIL_KEYS = ("email", "e-mail", "邮箱")


def trim_ws(value):
    return str(value if value is not None else "").replace("\u3000", " ").strip()


def norm_header(value):
    return re.sub(r"\s+", " ", trim_ws(value).lower())


def to_number(value):
    text = re.sub(r"[¥$€£,\s%]", "", trim_ws(value))
    if not re.fullmatch(r"[-+]?\d+(\.\d+)?", text or ""):
        return None
    number = float(text)
    return number if number == number else None


def fmt_num(number):
    rounded = int(round(number * 100)) / 100
    if rounded == int(rounded):
        return str(int(rounded))
    return str(rounded)


def make_iso(year, month, day):
    if year < 1900 or year > 2100 or month < 1 or month > 12 or day < 1 or day > 31:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_date(value):
    text = trim_ws(value)
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        return {"iso": make_iso(int(match[1]), int(match[2]), int(match[3])), "fmt": "iso"}
    match = re.fullmatch(r"(\d{4})[/.](\d{1,2})[/.](\d{1,2})", text)
    if match:
        return {"iso": make_iso(int(match[1]), int(match[2]), int(match[3])), "fmt": "yslash"}
    match = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", text)
    if match:
        first, second, year = int(match[1]), int(match[2]), int(match[3])
        if first > 12:
            return {"iso": make_iso(year, second, first), "fmt": "dmy"}
        if second > 12:
            return {"iso": make_iso(year, first, second), "fmt": "mdy"}
        return {"iso": make_iso(year, first, second), "fmt": "mdy"}
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})", text)
    if match:
        month = MONTHS.get(match[2].lower()[:3])
        return {"iso": make_iso(int(match[3]), month, int(match[1])), "fmt": "dmon"} if month else None
    match = re.fullmatch(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", text)
    if match:
        month = MONTHS.get(match[1].lower()[:3])
        return {"iso": make_iso(int(match[3]), month, int(match[2])), "fmt": "mond"} if month else None
    return None


def looks_date(value):
    text = trim_ws(value)
    return bool(
        re.fullmatch(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}", text)
        or re.fullmatch(r"(\d{1,2}\s+)?[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}", text)
    )


def quantile(values, portion):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * portion
    base = int(position)
    rest = position - base
    if base + 1 < len(ordered):
        return ordered[base] + rest * (ordered[base + 1] - ordered[base])
    return ordered[base]


def median(values):
    return quantile(values, 0.5)


def mode(values):
    counts = {}
    best = None
    best_n = 0
    for value in values:
        counts[value] = counts.get(value, 0) + 1
        if counts[value] > best_n:
            best_n = counts[value]
            best = value
    return best


def fold_text(value):
    return re.sub(r"\s+", " ", trim_ws(value).lower())


def header_is(header, keys):
    text = norm_header(header)
    if text in keys:
        return True
    return any(key in text for key in keys if len(key) >= 2)


def find_column(headers, keys, avoid=()):
    for index, header in enumerate(headers):
        text = norm_header(header)
        if any(word in text for word in avoid):
            continue
        if header_is(header, keys):
            return index
    return None


def infer_types(headers, rows):
    types = {}
    for index, _header in enumerate(headers):
        values = [trim_ws(row[index] if index < len(row) else "") for row in rows]
        values = [value for value in values if value]
        if not values:
            types[index] = "text"
            continue
        numbers = sum(1 for value in values if to_number(value) is not None)
        dates = sum(1 for value in values if to_number(value) is None and (parse_date(value) or looks_date(value)))
        if numbers / len(values) >= 0.6:
            types[index] = "number"
        elif dates / len(values) >= 0.6:
            types[index] = "date"
        else:
            types[index] = "text"
    return types


def row_key(row):
    return "\u0001".join(trim_ws(cell) for cell in row)


def analyze(headers, rows):
    issues = []
    by_type = {
        "missing": 0, "duplicate": 0, "date": 0, "outlier": 0,
        "space": 0, "spelling": 0, "iddup": 0, "amount": 0, "phone": 0, "email": 0,
    }
    types = infer_types(headers, rows)
    qty_i = find_column(headers, QTY_KEYS, avoid=("price", "单价", "amount", "金额"))
    price_i = find_column(headers, PRICE_KEYS)
    amount_i = find_column(headers, AMOUNT_KEYS, avoid=("price", "单价"))
    region_i = find_column(headers, REGION_KEYS)
    id_i = find_column(headers, ID_KEYS)
    phone_i = find_column(headers, PHONE_KEYS)
    email_i = find_column(headers, EMAIL_KEYS)

    def push(col, row, kind, original, suggestion):
        field = headers[col] if col is not None and col >= 0 else "*"
        issues.append({
            "key": f"{kind}_{row}_{col if col is not None else -1}",
            "type": kind,
            "row": row,
            "col": -1 if col is None else col,
            "field": field,
            "original": original,
            "suggestion": suggestion,
            "learned": False,
        })
        by_type[kind] += 1

    seen = {}
    for index, row in enumerate(rows):
        key = row_key(row)
        if key in seen:
            push(-1, index, "duplicate", "", {"kind": "removeRow", "value": "", "detail": ""})
        else:
            seen[key] = index

    if id_i is not None:
        groups = {}
        for index, row in enumerate(rows):
            value = trim_ws(row[id_i] if id_i < len(row) else "")
            if value:
                groups.setdefault(value, []).append(index)
        for value, indexes in groups.items():
            if len(indexes) < 2:
                continue
            first = row_key(rows[indexes[0]])
            for index in indexes[1:]:
                if row_key(rows[index]) == first:
                    continue
                push(id_i, index, "iddup", value, {"kind": "reviewId", "value": value, "detail": value})

    mismatched = set()
    explained = set()
    if qty_i is not None and price_i is not None and amount_i is not None:
        for index, row in enumerate(rows):
            qty = to_number(row[qty_i] if qty_i < len(row) else "")
            price = to_number(row[price_i] if price_i < len(row) else "")
            amount = to_number(row[amount_i] if amount_i < len(row) else "")
            if qty is None or price is None or amount is None:
                continue
            expected = qty * price
            detail = f"{fmt_num(qty)} × {fmt_num(price)} = {fmt_num(expected)}"
            if abs(amount - expected) > 0.05:
                mismatched.add(index)
                push(amount_i, index, "amount", trim_ws(row[amount_i]), {
                    "kind": "recalcAmount", "value": fmt_num(expected), "detail": detail,
                })
            else:
                explained.add(index)

    for col, header in enumerate(headers):
        kind = types[col]
        raw_cells = []
        for index, row in enumerate(rows):
            raw = row[col] if col < len(row) else ""
            raw_cells.append((index, "" if raw is None else str(raw)))
        non_empty = [(index, trim_ws(raw)) for index, raw in raw_cells if trim_ws(raw)]

        for index, raw in raw_cells:
            trimmed = trim_ws(raw)
            if raw != trimmed and trimmed:
                push(col, index, "space", raw, {"kind": "trim", "value": trimmed, "detail": trimmed})
            elif trimmed == "":
                if kind == "number":
                    nums = [to_number(value) for _, value in non_empty]
                    nums = [value for value in nums if value is not None]
                    suggestion = (
                        {"kind": "fillMedian", "value": fmt_num(median(nums)), "detail": fmt_num(median(nums))}
                        if nums else {"kind": "fillMode", "value": "", "detail": ""}
                    )
                else:
                    common = mode([value for _, value in non_empty]) or ""
                    suggestion = {"kind": "fillMode", "value": common, "detail": common}
                push(col, index, "missing", "", suggestion)

        if kind == "date":
            parsed = []
            for index, value in non_empty:
                parsed_date = parse_date(value)
                invalid = looks_date(value) and (not parsed_date or not parsed_date.get("iso"))
                parsed.append((index, value, parsed_date, invalid))
            valid = [item for item in parsed if not item[3] and item[2] and item[2].get("iso")]
            fmt_counts = {}
            best_fmt = None
            best_n = 0
            for _index, _value, parsed_date, _invalid in valid:
                fmt_counts[parsed_date["fmt"]] = fmt_counts.get(parsed_date["fmt"], 0) + 1
                if fmt_counts[parsed_date["fmt"]] > best_n:
                    best_n = fmt_counts[parsed_date["fmt"]]
                    best_fmt = parsed_date["fmt"]
            common_iso = mode([item[2]["iso"] for item in valid]) if valid else ""
            for index, value, parsed_date, invalid in parsed:
                if invalid:
                    push(col, index, "date", value, {"kind": "commonDate", "value": common_iso or "", "detail": common_iso or ""})
                elif parsed_date and parsed_date["fmt"] != best_fmt:
                    push(col, index, "date", value, {"kind": "convertDate", "value": parsed_date["iso"], "detail": parsed_date["iso"]})

        if kind == "number":
            nums = [to_number(value) for _, value in non_empty]
            nums = [value for value in nums if value is not None]
            if len(nums) >= 5:
                q1, q3 = quantile(nums, 0.25), quantile(nums, 0.75)
                iqr = q3 - q1
                if iqr > 0:
                    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                    mid = fmt_num(median(nums))
                    for index, value in non_empty:
                        number = to_number(value)
                        if number is None or low <= number <= high:
                            continue
                        if col == amount_i and (index in mismatched or index in explained):
                            continue
                        push(col, index, "outlier", value, {"kind": "fillMedian", "value": mid, "detail": mid})

        skip_spelling = col in {id_i, phone_i, email_i} or kind != "text"
        if not skip_spelling and len(non_empty) >= 4:
            folded = {}
            for index, value in non_empty:
                folded.setdefault(fold_text(value), []).append((index, value))
            distinct = len({value for _, value in non_empty})
            if distinct <= max(12, int(len(non_empty) * 0.5)):
                for _key, group in folded.items():
                    variants = {value for _, value in group}
                    if len(variants) < 2:
                        continue
                    chosen = mode([value for _, value in group])
                    for index, value in group:
                        if value != chosen:
                            push(col, index, "spelling", value, {"kind": "normalizeText", "value": chosen, "detail": chosen})

    if phone_i is not None:
        for index, row in enumerate(rows):
            raw = row[phone_i] if phone_i < len(row) else ""
            text = trim_ws(raw)
            if not text:
                continue
            digits = re.sub(r"[^\d]", "", text)
            if 7 <= len(digits) <= 15 and digits != text:
                push(phone_i, index, "phone", text, {"kind": "normalizePhone", "value": digits, "detail": digits})
            elif not (7 <= len(digits) <= 15):
                push(phone_i, index, "phone", text, {"kind": "normalizePhone", "value": digits, "detail": digits})

    if email_i is not None:
        for index, row in enumerate(rows):
            raw = row[email_i] if email_i < len(row) else ""
            text = trim_ws(raw)
            if not text:
                continue
            cleaned = re.sub(r"\s+", "", text).lower()
            if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cleaned) and cleaned == text:
                continue
            push(email_i, index, "email", text, {"kind": "normalizeEmail", "value": cleaned, "detail": cleaned})

    return {
        "issues": issues,
        "by_type": by_type,
        "column_types": {str(key): value for key, value in types.items()},
        "columns": {
            "qty": qty_i, "price": price_i, "amount": amount_i, "region": region_i,
            "id": id_i, "phone": phone_i, "email": email_i,
        },
    }


def apply_learned(issues, rules):
    applied = []
    for issue in issues:
        rule = rules.get(f"{issue['type']}|{issue['field']}")
        if not rule:
            applied.append(issue)
            continue
        copied = dict(issue)
        copied["suggestion"] = dict(rule)
        copied["learned"] = True
        applied.append(copied)
    return applied


def build_cleaned(headers, rows, issues, decisions):
    removed = set()
    fixed = ignored = unresolved = duplicates_removed = 0
    for issue in issues:
        decision = decisions.get(issue["key"])
        if not decision:
            unresolved += 1
            continue
        if decision["action"] == "ignore":
            ignored += 1
        elif decision["action"] == "accept" and issue["type"] == "duplicate":
            removed.add(issue["row"])
            duplicates_removed += 1
        else:
            fixed += 1

    index_map = {}
    cleaned = []
    for index, row in enumerate(rows):
        if index in removed:
            continue
        index_map[index] = len(cleaned)
        cleaned.append(list(row))

    for issue in issues:
        decision = decisions.get(issue["key"])
        if not decision or issue["type"] == "duplicate" or decision["action"] == "ignore":
            continue
        if issue["row"] in removed or issue["col"] < 0:
            continue
        if issue["suggestion"].get("kind") == "reviewId" and decision["action"] == "accept":
            continue
        value = issue["suggestion"].get("value") if decision["action"] == "accept" else decision.get("value")
        cleaned[index_map[issue["row"]]][issue["col"]] = "" if value is None else str(value)

    return {
        "headers": headers,
        "rows": cleaned,
        "fixed": fixed,
        "ignored": ignored,
        "unresolved": unresolved,
        "duplicates_removed": duplicates_removed,
    }


def quality_score(row_count, col_count, issues, decisions):
    cells = max(1, row_count * max(1, col_count))
    unresolved = sum(1 for issue in issues if issue["key"] not in decisions)
    score = 100 * (1 - unresolved / cells)
    return max(0, round(score * 10) / 10)


def explain(issue, lang):
    row = issue["row"] + 1
    field = issue["field"]
    original = issue["original"] if issue["original"] != "" else ("(空)" if lang == "zh" else "(empty)")
    suggestion = issue["suggestion"]
    value = suggestion.get("value") or ""
    detail = suggestion.get("detail") or value
    kind = issue["type"]
    if lang == "zh":
        if kind == "missing":
            return f"第 {row} 行「{field}」是空的。建议填「{value or '待确认'}」，空着会影响筛选和合计。"
        if kind == "duplicate":
            return f"第 {row} 行和前面某一行完全一样。两行都留着会把同一笔计算两次。"
        if kind == "date":
            return f"第 {row} 行「{field}」是「{original}」，和这一列大多数日期不是同一种写法。建议改成 {value}。"
        if kind == "outlier":
            return f"第 {row} 行「{field}」的值 {original} 偏离这一列的正常范围。中位数是 {value}。它也可能是一笔真的大单，请你决定。"
        if kind == "space":
            return f"第 {row} 行「{field}」首尾有空格，现在写成「{original}」。建议改成「{value}」。"
        if kind == "spelling":
            return f"第 {row} 行「{field}」写成「{original}」，这一列里更常见的写法是「{value}」。"
        if kind == "iddup":
            return f"编号「{original}」出现了不止一次，但这些行并不完全相同。系统不会自动删除，请你判断是不是重复下单。"
        if kind == "amount":
            return f"第 {row} 行金额对不上：{detail}，表上写的是 {original}。不要直接改成中位数。"
        if kind == "phone":
            return f"第 {row} 行「{field}」是「{original}」。建议整理成数字 {value or '（没有足够的数字）'}。"
        if kind == "email":
            return f"第 {row} 行「{field}」是「{original}」，不像一个邮箱。"
        if kind == "enum":
            return f"第 {row} 行「{field}」写成「{original}」，不在模板允许的写法里。建议改成「{value}」。"
        if kind == "range":
            return f"第 {row} 行「{field}」的值是 {original}。{detail or '它不在模板允许的范围内'}。建议改成 {value}。"
        return f"第 {row} 行需要你看一眼。"
    if kind == "missing":
        return f"Row {row}, {field} is empty. Suggested fill: {value or 'needs a value'}."
    if kind == "duplicate":
        return f"Row {row} is an exact copy of an earlier row. Keeping both would count the same record twice."
    if kind == "date":
        return f"Row {row}, {field} is '{original}', which does not match the usual date format. Suggested: {value}."
    if kind == "outlier":
        return f"Row {row}, {field} is {original}, outside the usual range. The median is {value}. It might be a real large order."
    if kind == "space":
        return f"Row {row}, {field} has extra spaces ('{original}'). Suggested: '{value}'."
    if kind == "spelling":
        return f"Row {row}, {field} is '{original}'. The more common spelling in this column is '{value}'."
    if kind == "iddup":
        return f"ID '{original}' appears more than once, but the rows are not identical. Nothing is deleted automatically."
    if kind == "amount":
        return f"Row {row} amount does not match the formula: {detail}. The cell says {original}. Do not replace it with the median."
    if kind == "phone":
        return f"Row {row}, {field} is '{original}'. Suggested digits: {value or '(not enough digits)'}."
    if kind == "email":
        return f"Row {row}, {field} is '{original}', which does not look like an email."
    if kind == "enum":
        return f"Row {row}, {field} is '{original}', which is not an allowed value. Suggested: '{value}'."
    if kind == "range":
        return f"Row {row}, {field} is {original}. {detail or 'It is outside the allowed range.'} Suggested: {value}."
    return f"Row {row} needs a decision."


def to_csv(headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return "\ufeff" + buffer.getvalue()


def cell_str(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def table_from_rows(raw_rows):
    rows = []
    for row in raw_rows:
        cells = [cell_str(cell) for cell in row]
        if any(trim_ws(cell) for cell in cells):
            rows.append(cells)
    if not rows:
        return [], [], False
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    headers = [trim_ws(cell) or f"Column {index + 1}" for index, cell in enumerate(rows[0])]
    data = rows[1:]
    truncated = len(data) > ROW_CAP
    return headers, data[:ROW_CAP], truncated


def parse_upload(filename, payload):
    lower = filename.lower()
    if lower.endswith(".csv") or lower.endswith(".txt"):
        text = payload.decode("utf-8-sig", errors="replace")
        parsed = list(csv.reader(io.StringIO(text)))
        return table_from_rows(parsed)
    if lower.endswith(".xlsx"):
        import openpyxl
        book = openpyxl.load_workbook(io.BytesIO(payload), data_only=True, read_only=True)
        sheet = book.worksheets[0]
        parsed = [list(row) for row in sheet.iter_rows(values_only=True)]
        book.close()
        return table_from_rows(parsed)
    if lower.endswith(".xls"):
        import xlrd
        book = xlrd.open_workbook(file_contents=payload)
        sheet = book.sheet_by_index(0)
        parsed = []
        for row_index in range(sheet.nrows):
            values = []
            for col_index in range(sheet.ncols):
                cell = sheet.cell(row_index, col_index)
                if cell.ctype == xlrd.XL_CELL_DATE:
                    values.append(xlrd.xldate_as_datetime(cell.value, book.datemode).strftime("%Y-%m-%d"))
                elif cell.ctype == xlrd.XL_CELL_NUMBER and float(cell.value).is_integer():
                    values.append(str(int(cell.value)))
                else:
                    values.append("" if cell.value is None else str(cell.value))
            parsed.append(values)
        return table_from_rows(parsed)
    raise ValueError("BAD_TYPE")


ALLOWED_RULES = {"not_empty", "unique", "enum", "date", "phone", "email", "equals_product", "number_range", "non_negative", "positive"}


def column_index(headers, name):
    if not name:
        return None
    target = norm_header(name)
    for index, header in enumerate(headers):
        if norm_header(header) == target:
            return index
    return None


def normalize_rules(raw):
    rules = []
    if not isinstance(raw, list):
        return rules
    for item in raw[:40]:
        if not isinstance(item, dict) or item.get("type") not in ALLOWED_RULES:
            continue
        values = [str(value) for value in (item.get("values") or [])][:30]
        try:
            low = None if item.get("min") is None else float(item.get("min"))
            high = None if item.get("max") is None else float(item.get("max"))
        except (TypeError, ValueError):
            low, high = None, None
        rules.append({
            "type": item["type"],
            "field": str(item.get("field") or "").strip()[:80],
            "text": str(item.get("text") or "").strip()[:200],
            "values": values,
            "qty": str(item.get("qty") or "").strip()[:80],
            "price": str(item.get("price") or "").strip()[:80],
            "min": low,
            "max": high,
        })
    return rules


def _push_rule(issues, kind, row, col, field, original, suggestion):
    issues.append({
        "key": f"tpl_{kind}_{row}_{col}",
        "type": kind,
        "row": row,
        "col": col,
        "field": field,
        "original": original,
        "suggestion": suggestion,
        "learned": False,
    })


def apply_template_rules(headers, rows, rules):
    issues = []
    rules = normalize_rules(rules)
    for rule in rules:
        kind = rule["type"]
        if kind == "equals_product":
            qty_i = column_index(headers, rule["qty"])
            price_i = column_index(headers, rule["price"])
            amount_i = column_index(headers, rule["field"])
            if None in (qty_i, price_i, amount_i):
                continue
            for index, row in enumerate(rows):
                qty = to_number(row[qty_i])
                price = to_number(row[price_i])
                amount = to_number(row[amount_i])
                if qty is None or price is None or amount is None:
                    continue
                expected = qty * price
                if abs(amount - expected) <= 0.05:
                    continue
                detail = f"{fmt_num(qty)} × {fmt_num(price)} = {fmt_num(expected)}"
                _push_rule(issues, "amount", index, amount_i, headers[amount_i], trim_ws(row[amount_i]), {
                    "kind": "recalcAmount", "value": fmt_num(expected), "detail": detail,
                })
            continue
        col = column_index(headers, rule["field"])
        if col is None:
            continue
        field = headers[col]
        if kind == "unique":
            groups = {}
            for index, row in enumerate(rows):
                value = trim_ws(row[col])
                if value:
                    groups.setdefault(value, []).append(index)
            for value, indexes in groups.items():
                if len(indexes) < 2:
                    continue
                first = row_key(rows[indexes[0]])
                for index in indexes[1:]:
                    if row_key(rows[index]) == first:
                        continue
                    _push_rule(issues, "iddup", index, col, field, value, {"kind": "reviewId", "value": value, "detail": value})
            continue
        for index, row in enumerate(rows):
            raw = row[col] if col < len(row) else ""
            text = trim_ws(raw)
            if kind == "not_empty":
                if text == "":
                    _push_rule(issues, "missing", index, col, field, "", {"kind": "fillMode", "value": "", "detail": rule["text"]})
            elif kind == "enum":
                allowed = rule["values"]
                if not text or text in allowed:
                    continue
                folded = {fold_text(value): value for value in allowed}
                chosen = folded.get(fold_text(text)) or (allowed[0] if allowed else "")
                _push_rule(issues, "enum", index, col, field, text, {"kind": "normalizeText", "value": chosen, "detail": "、".join(allowed)})
            elif kind == "date":
                parsed = parse_date(text) if text else None
                if not text:
                    continue
                if not parsed or not parsed.get("iso"):
                    _push_rule(issues, "date", index, col, field, text, {"kind": "commonDate", "value": "", "detail": rule["text"]})
                elif parsed["fmt"] != "iso":
                    _push_rule(issues, "date", index, col, field, text, {"kind": "convertDate", "value": parsed["iso"], "detail": parsed["iso"]})
            elif kind == "phone":
                if not text:
                    continue
                digits = re.sub(r"[^\d]", "", text)
                if digits == text and 7 <= len(digits) <= 15:
                    continue
                _push_rule(issues, "phone", index, col, field, text, {"kind": "normalizePhone", "value": digits, "detail": digits})
            elif kind == "email":
                if not text:
                    continue
                cleaned = re.sub(r"\s+", "", text).lower()
                if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cleaned) and cleaned == text:
                    continue
                _push_rule(issues, "email", index, col, field, text, {"kind": "normalizeEmail", "value": cleaned, "detail": cleaned})
            elif kind in {"number_range", "non_negative", "positive"}:
                if text == "":
                    continue
                number = to_number(text)
                if number is None:
                    _push_rule(issues, "range", index, col, field, text, {"kind": "custom", "value": "", "detail": rule["text"]})
                    continue
                if kind == "non_negative" and number < 0:
                    _push_rule(issues, "range", index, col, field, text, {"kind": "custom", "value": "0", "detail": rule["text"] or "数量不能是负数"})
                elif kind == "positive" and number <= 0:
                    _push_rule(issues, "range", index, col, field, text, {"kind": "custom", "value": "", "detail": rule["text"] or "必须大于 0"})
                elif kind == "number_range":
                    low = 0 if rule["min"] is None else rule["min"]
                    high = 100 if rule["max"] is None else rule["max"]
                    if number < low or number > high:
                        suggested = low if number < low else high
                        _push_rule(issues, "range", index, col, field, text, {
                            "kind": "custom", "value": fmt_num(suggested), "detail": rule["text"] or f"应在 {fmt_num(low)} 到 {fmt_num(high)}",
                        })
    return issues


def merge_issues(base, extra):
    kept = list(base)
    occupied = {(issue["row"], issue["col"], issue["type"]) for issue in kept}
    covered = {(issue["row"], issue["col"]) for issue in kept if issue["type"] in {"amount", "phone", "email", "date", "missing", "iddup"}}
    for issue in extra:
        slot = (issue["row"], issue["col"], issue["type"])
        if slot in occupied:
            continue
        if issue["type"] in {"amount", "phone", "email", "date", "missing", "iddup"} and (issue["row"], issue["col"]) in covered:
            continue
        if issue["type"] == "enum":
            kept = [item for item in kept if not (item["row"] == issue["row"] and item["col"] == issue["col"] and item["type"] == "spelling")]
        if issue["type"] in {"range", "amount", "phone"}:
            kept = [item for item in kept if not (item["row"] == issue["row"] and item["col"] == issue["col"] and item["type"] == "outlier")]
        kept.append(issue)
        occupied.add(slot)
        if issue["type"] in {"amount", "phone", "email", "date", "missing", "iddup"}:
            covered.add((issue["row"], issue["col"]))
    blocked = {(item["row"], item["col"]) for item in kept if item["type"] in {"phone", "amount", "range"}}
    kept = [item for item in kept if not (item["type"] == "outlier" and (item["row"], item["col"]) in blocked)]
    return kept


def guess_rules(headers, rows, note):
    text = note or ""
    rules = []
    joined = " ".join(headers)
    blob = f"{joined} {text}"
    if any(name in blob for name in ("金额", "Amount")) and any(name in blob for name in ("数量", "单价", "Units")):
        qty = next((header for header in headers if header in {"数量", "Units"}), "")
        price = next((header for header in headers if header in {"单价", "Unit Price"}), "")
        amount = next((header for header in headers if header in {"金额", "Amount"}), "")
        if qty and price and amount:
            rules.append({"type": "equals_product", "field": amount, "qty": qty, "price": price, "text": "金额必须等于数量乘单价"})
    for header in headers:
        folded = norm_header(header)
        if any(word in folded for word in ("phone", "mobile", "tel", "手机", "电话")):
            rules.append({"type": "phone", "field": header, "text": f"{header}应整理成数字"})
        if any(word in folded for word in ("email", "邮箱")):
            rules.append({"type": "email", "field": header, "text": f"{header}要像一个邮箱"})
        if any(word in folded for word in ("date", "日期")):
            rules.append({"type": "date", "field": header, "text": f"{header}必须能读"})
        if any(word in folded for word in ("订单号", "单号", "货号", "学号", "order id")):
            rules.append({"type": "not_empty", "field": header, "text": f"{header}不能为空"})
            rules.append({"type": "unique", "field": header, "text": f"{header}不能重复"})
    for index, header in enumerate(headers):
        values = [trim_ws(row[index]) for row in rows if trim_ws(row[index])]
        distinct = list(dict.fromkeys(values))
        if 1 < len(distinct) <= 8 and len(values) >= 3 and len(distinct) / len(values) <= 0.6:
            if not any(rule["field"] == header for rule in rules):
                rules.append({"type": "enum", "field": header, "values": distinct, "text": f"{header}只能是模板里出现过的写法"})
    if "负数" in text or "小于 0" in text:
        for header in headers:
            if "数量" in header:
                rules.append({"type": "non_negative", "field": header, "text": "数量不能是负数"})
    if "大于 0" in text:
        for header in headers:
            if "金额" in header:
                rules.append({"type": "positive", "field": header, "text": "金额必须大于 0"})
    if "0" in text and "100" in text:
        for header in headers:
            if "分" in header:
                rules.append({"type": "number_range", "field": header, "min": 0, "max": 100, "text": "分数必须在 0 到 100"})
    return normalize_rules(rules)


def rules_from_model_text(content, headers):
    import json
    raw = content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[-1]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    items = parsed.get("rules") if isinstance(parsed, dict) else parsed
    rules = normalize_rules(items)
    known = {norm_header(header) for header in headers}
    kept = []
    for rule in rules:
        names = [rule["field"], rule["qty"], rule["price"]]
        if all(not name or norm_header(name) in known for name in names):
            kept.append(rule)
    return kept


def is_safe_auto(issue):
    """只自动接受写法唯一、不需要猜业务的改动。"""
    suggestion = issue.get("suggestion") or {}
    kind = suggestion.get("kind")
    value = suggestion.get("value") or ""
    original = issue.get("original") or ""
    if kind == "trim" and value:
        return True
    if kind == "convertDate" and value:
        return True
    if kind == "normalizePhone" and value.isdigit() and 7 <= len(value) <= 15:
        return True
    if kind == "normalizeEmail" and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        return True
    if kind == "normalizeText" and value and fold_text(original) == fold_text(value):
        return True
    return False


