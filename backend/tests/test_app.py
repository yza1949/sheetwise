"""清洗规则和一次完整的接口走通。"""

import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = (ROOT / "sample" / "sales_demo.csv").read_text(encoding="utf-8")

os.environ["SHEETWISE_DATA"] = tempfile.mkdtemp()
os.environ["SHEETWISE_DB"] = os.path.join(os.environ["SHEETWISE_DATA"], "test.db")
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"

import sys
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from cleaning import analyze, parse_upload
from main import app


class CleaningTests(unittest.TestCase):
    def test_sample_finds_the_new_checks(self):
        headers, rows, truncated = parse_upload("sales_demo.csv", SAMPLE.encode("utf-8"))
        self.assertFalse(truncated)
        result = analyze(headers, rows)
        kinds = {issue["type"] for issue in result["issues"]}
        for expected in ("missing", "duplicate", "date", "outlier", "space", "spelling", "iddup", "amount", "phone", "email"):
            self.assertIn(expected, kinds)
        amount_rows = {issue["row"] for issue in result["issues"] if issue["type"] == "amount"}
        outlier_rows = {issue["row"] for issue in result["issues"] if issue["type"] == "outlier"}
        self.assertTrue(amount_rows)
        self.assertTrue(outlier_rows.isdisjoint(amount_rows))


class ApiTests(unittest.TestCase):
    def test_two_users_cannot_see_each_other(self):
        client = TestClient(app)
        admin = client.post("/api/auth/register", json={"name": "Mia", "email": "mia@shop.com", "password": "secret1"})
        self.assertEqual(admin.status_code, 200)
        self.assertEqual(admin.json()["role"], "admin")
        created = client.post("/api/datasets/sample", json={"question": "华北的椅子卖了多少", "lang": "zh"})
        self.assertEqual(created.status_code, 200)
        dataset_id = created.json()["id"]
        self.assertIn("amount", created.json()["byType"])
        self.assertEqual(created.json()["templateName"], "销售订单")
        self.assertTrue(created.json()["log"])
        self.assertEqual(created.json()["engine"], "规则引擎")
        client.post("/api/auth/logout")

        member = TestClient(app)
        registered = member.post("/api/auth/register", json={"name": "Leo", "email": "leo@shop.com", "password": "secret1"})
        self.assertEqual(registered.json()["role"], "member")
        listing = member.get("/api/datasets")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json(), [])
        hidden = member.get(f"/api/datasets/{dataset_id}")
        self.assertEqual(hidden.status_code, 404)

        client = TestClient(app)
        client.post("/api/auth/login", json={"email": "mia@shop.com", "password": "secret1"})
        detail = client.get(f"/api/datasets/{dataset_id}?lang=zh").json()
        for issue in detail["issues"]:
            client.post(
                f"/api/datasets/{dataset_id}/anomalies/{issue['id']}",
                json={"action": "accept"},
            )
        done = client.post(f"/api/datasets/{dataset_id}/complete", json={"lang": "zh"})
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(done.json()["status"], "done")
        self.assertTrue(done.json()["answer"]["zh"]["text"])
        downloaded = client.get(f"/api/datasets/{dataset_id}/download")
        self.assertEqual(downloaded.status_code, 200)
        self.assertIn("订单号", downloaded.text)
        templates = client.get("/api/templates")
        self.assertEqual(templates.status_code, 200)
        self.assertEqual(len(templates.json()), 5)
        analyzed = client.post("/api/templates/sales/analyze")
        self.assertEqual(analyzed.status_code, 200)
        self.assertEqual(analyzed.json()["source"], "builtin")
        self.assertTrue(any(rule["type"] == "equals_product" for rule in analyzed.json()["rules"]))
        usage = client.get("/api/usage")
        self.assertEqual(usage.json()["usedCalls"], 0)
        self.assertEqual(usage.json()["callLimit"], 30)


if __name__ == "__main__":
    unittest.main()
