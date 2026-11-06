"""五份模板的中英示例，各约 50 行。大部分是对的，只夹少量要人看的错。"""

import csv
import io


def _csv(headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def _money(qty, price):
    value = qty * price
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text


def _sales(en):
    headers = ["Order ID", "Date", "Region", "Product", "Quantity", "Unit Price", "Amount"] if en else ["订单号", "日期", "地区", "商品", "数量", "单价", "金额"]
    regions = ["North", "South", "East", "West"] if en else ["华北", "华南", "华东", "华西"]
    products = ["Lamp", "Chair", "Keyboard", "Monitor"] if en else ["台灯", "椅子", "键盘", "显示器"]
    prices = [25.5, 89, 18, 150]
    rows = []
    for index in range(50):
        qty = (index % 5) + 1
        price = prices[index % 4]
        rows.append([
            f"ORD-{1001 + index}",
            f"2024-03-{(index % 27) + 1:02d}",
            regions[index % 4],
            products[index % 4],
            str(qty),
            _money(1, price),
            _money(qty, price),
        ])
    rows[2][2] = "north" if en else rows[2][2] + " "
    rows[4][1] = "03/05/2024" if en else "2024/3/5"
    rows[6][3] = " " + rows[6][3] + " "
    rows[12][6] = "99999"
    rows[22][0] = rows[21][0]
    rows[22][3] = products[0]
    rows[33][2] = "Central" if en else "海外"
    rows[41][1] = "2024-13-40"
    rows[48][4] = ""
    rules = [
        {"type": "not_empty", "field": headers[0], "text": "Order ID is required" if en else "订单号不能为空"},
        {"type": "unique", "field": headers[0], "text": "Order ID cannot repeat" if en else "订单号不能重复"},
        {"type": "date", "field": headers[1], "text": "Date must be readable" if en else "日期要能读成同一种写法"},
        {"type": "enum", "field": headers[2], "text": "Region must be one of the template values" if en else "地区只能是模板里出现过的写法", "values": regions},
        {"type": "not_empty", "field": headers[4], "text": "Quantity is required" if en else "数量不能为空"},
        {"type": "equals_product", "field": headers[6], "qty": headers[4], "price": headers[5], "text": "Amount must equal quantity times unit price" if en else "金额必须等于数量乘单价"},
    ]
    return _finish(
        "sales",
        "Sales orders" if en else "销售订单",
        "Order IDs stay unique, amount equals quantity times price, and region stays inside the template list." if en else "订单号不能重复，金额必须等于数量乘单价，地区只能是模板里出现过的写法。",
        "Use one date style. Regions are only North, South, East and West. Amount = quantity × unit price." if en else "日期用同一种写法。地区只允许华北、华南、华东、华西。金额 = 数量 × 单价。订单号不能空，也不能两条不一样的记录用同一个号。",
        headers, rows[:4], rules, rows, en,
    )


def _contacts(en):
    headers = ["Name", "Phone", "Email", "City"] if en else ["姓名", "手机", "邮箱", "城市"]
    cities = ["Shanghai", "Beijing", "Guangzhou", "Shenzhen"] if en else ["上海", "北京", "广州", "深圳"]
    names = ["Zhou Ming", "Li Na", "Chen Feng", "Wang Min"] if en else ["周明", "李娜", "陈峰", "王敏"]
    rows = []
    for index in range(50):
        phone = f"138{index + 10000000:08d}"[-11:]
        rows.append([names[index % 4], phone, f"user{index + 1}@shop.com", cities[index % 4]])
    rows[3][1] = "138-0000-0003"
    rows[5][3] = rows[5][3] + " "
    rows[8][2] = "li @shop.com" if en else "li @shop.com"
    rows[14][1] = "12345"
    rows[23][1] = rows[22][1]
    rows[23][0] = "Sam" if en else "赵六"
    rows[34][3] = "Tokyo" if en else "东京"
    rows[44][0] = ""
    rows[46][2] = "not-an-email"
    rules = [
        {"type": "not_empty", "field": headers[0], "text": "Name is required" if en else "姓名不能为空"},
        {"type": "phone", "field": headers[1], "text": "Phone should be digits" if en else "手机应整理成数字"},
        {"type": "email", "field": headers[2], "text": "Email needs @ and a domain" if en else "邮箱要包含 @ 和域名"},
        {"type": "unique", "field": headers[1], "text": "The same phone should not appear twice" if en else "同一个手机号不要出现两次"},
        {"type": "enum", "field": headers[3], "text": "City must be one of the template cities" if en else "城市只能是模板里的四个", "values": cities},
    ]
    return _finish(
        "contacts",
        "Contacts" if en else "客户联系人",
        "Phones are digits, emails look like emails, and the same phone is not used twice." if en else "手机只保留数字，邮箱要像邮箱，同一个手机号不要出现两次。",
        "Phone is 11 digits. Email contains @. Cities are only the ones in the template." if en else "手机是 11 位数字。邮箱里要有 @。城市只能是上海、北京、广州、深圳。",
        headers, rows[:3], rules, rows, en,
    )


def _stock(en):
    headers = ["SKU", "Product", "Warehouse", "Quantity"] if en else ["货号", "商品", "仓库", "数量"]
    warehouses = ["Shanghai", "Beijing", "Guangzhou"] if en else ["上海仓", "北京仓", "广州仓"]
    products = ["Lamp", "Chair", "Keyboard", "Monitor"] if en else ["台灯", "椅子", "键盘", "显示器"]
    rows = []
    for index in range(50):
        rows.append([f"SKU-{index + 1:02d}", products[index % 4], warehouses[index % 3], str(10 + (index % 7))])
    rows[4][2] = rows[4][2] + " "
    rows[11][3] = "-3"
    rows[19][0] = rows[18][0]
    rows[19][3] = "8"
    rows[29][2] = "Hangzhou" if en else "杭州仓"
    rows[37][3] = ""
    rules = [
        {"type": "not_empty", "field": headers[0], "text": "SKU is required" if en else "货号不能为空"},
        {"type": "unique", "field": headers[0], "text": "SKU cannot repeat" if en else "货号不能重复"},
        {"type": "enum", "field": headers[2], "text": "Warehouse must match the template" if en else "仓库只能是模板里的三个", "values": warehouses},
        {"type": "non_negative", "field": headers[3], "text": "Quantity cannot be negative" if en else "数量不能是负数"},
        {"type": "not_empty", "field": headers[3], "text": "Quantity is required" if en else "数量不能为空"},
    ]
    return _finish(
        "stock",
        "Inventory" if en else "库存",
        "SKU is unique, quantity is not negative, and the warehouse name matches the template." if en else "货号唯一，数量不能是负数，仓库名要和模板一致。",
        "Quantity must be zero or more. Warehouses are only the ones listed in the template." if en else "数量必须大于或等于 0。仓库只能是上海仓、北京仓、广州仓。",
        headers, rows[:3], rules, rows, en,
    )


def _expense(en):
    headers = ["Receipt", "Date", "Category", "Amount", "Note"] if en else ["单号", "日期", "类别", "金额", "说明"]
    categories = ["Transport", "Meals", "Lodging", "Office"] if en else ["交通", "餐饮", "住宿", "办公"]
    notes = ["Metro", "Lunch", "Hotel", "Pens"] if en else ["地铁", "午餐", "出差", "文具"]
    rows = []
    for index in range(50):
        rows.append([
            f"EXP-{index + 1:03d}",
            f"2024-04-{(index % 27) + 1:02d}",
            categories[index % 4],
            str(20 + index),
            notes[index % 4],
        ])
    rows[5][1] = "04/06/2024" if en else "2024/4/6"
    rows[8][2] = "meals" if en else rows[8][2] + " "
    rows[15][3] = "-15"
    rows[24][0] = rows[23][0]
    rows[24][3] = "40"
    rows[32][2] = "Gift" if en else "礼品"
    rows[42][1] = "2024-13-01"
    rows[47][3] = ""
    rules = [
        {"type": "unique", "field": headers[0], "text": "Receipt ID cannot repeat" if en else "报销单号不能重复"},
        {"type": "date", "field": headers[1], "text": "Date must be readable" if en else "日期必须能读"},
        {"type": "enum", "field": headers[2], "text": "Category must be one of the template values" if en else "类别只能是交通、餐饮、住宿、办公", "values": categories},
        {"type": "not_empty", "field": headers[3], "text": "Amount is required" if en else "金额不能为空"},
        {"type": "positive", "field": headers[3], "text": "Amount must be greater than 0" if en else "金额必须大于 0"},
    ]
    return _finish(
        "expense",
        "Expenses" if en else "报销",
        "Amount is above zero, category stays inside the template, and the date can be read." if en else "金额要大于 0，类别只能是模板里的几种，日期必须能读。",
        "Allowed categories are listed in the template. Amount must be greater than 0." if en else "类别只允许交通、餐饮、住宿、办公。金额必须大于 0。单号不能重复。",
        headers, rows[:4], rules, rows, en,
    )


def _scores(en):
    headers = ["Student ID", "Name", "Class", "Score"] if en else ["学号", "姓名", "班级", "分数"]
    classes = ["Class A", "Class B"] if en else ["一班", "二班"]
    names = ["Zhou Ming", "Li Na", "Chen Feng", "Wang Min"] if en else ["周明", "李娜", "陈峰", "王敏"]
    rows = []
    for index in range(50):
        rows.append([f"S{1001 + index}", names[index % 4], classes[index % 2], str(70 + (index % 25))])
    rows[4][2] = "class a" if en else rows[4][2] + " "
    rows[9][1] = " " + rows[9][1]
    rows[16][3] = "120"
    rows[26][3] = "-4"
    rows[35][0] = rows[34][0]
    rows[35][3] = "90"
    rows[43][0] = ""
    rows[49][2] = "Class C" if en else "三班"
    rules = [
        {"type": "not_empty", "field": headers[0], "text": "Student ID is required" if en else "学号不能为空"},
        {"type": "unique", "field": headers[0], "text": "Student ID cannot repeat" if en else "学号不能重复"},
        {"type": "enum", "field": headers[2], "text": "Class must match the template" if en else "班级只能是一班或二班", "values": classes},
        {"type": "number_range", "field": headers[3], "min": 0, "max": 100, "text": "Score must be from 0 to 100" if en else "分数必须在 0 到 100"},
    ]
    return _finish(
        "scores",
        "Scores" if en else "成绩",
        "Student ID is unique, score stays between 0 and 100, and class matches the template." if en else "学号不能空、不能重复，分数在 0 到 100，班级写法跟模板一致。",
        "Score must be from 0 to 100. Classes are only the ones in the template." if en else "学号不能空也不能重复。分数必须在 0 到 100。班级只能是一班或二班。",
        headers, rows[:4], rules, rows, en,
    )


def _finish(slug, name, summary, note, headers, sample, rules, rows, en):
    return {
        "slug": slug,
        "name": name,
        "summary": summary,
        "note": note,
        "headers": headers,
        "sample": sample,
        "rules": rules,
        "dirty": _csv(headers, rows),
        "lang": "en" if en else "zh",
    }


_BUILDERS = {
    "sales": _sales,
    "contacts": _contacts,
    "stock": _stock,
    "expense": _expense,
    "scores": _scores,
}


def pack(slug, lang="zh"):
    builder = _BUILDERS.get(slug)
    if not builder:
        return None
    return builder(lang == "en")


def all_packs(lang="zh"):
    return [pack(slug, lang) for slug in _BUILDERS]
