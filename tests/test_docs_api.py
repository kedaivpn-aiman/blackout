#!/usr/bin/env python3
import json
import re
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT_DIR / "docs" / "api.md"


class TestDocsApi(unittest.TestCase):
    def setUp(self):
        self.text = DOC_PATH.read_text(encoding="utf-8")

    def test_json_blocks_are_valid(self):
        # Extract code blocks labeled ```json ... ```
        blocks = re.findall(r"```json\s*\n(.*?)\n```", self.text, re.DOTALL)
        self.assertGreaterEqual(len(blocks), 8, "Expected at least 8 json code blocks")
        for i, block in enumerate(blocks):
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                self.fail(f"JSON code block #{i+1} is invalid JSON: {exc}\nContent:\n{block}")

    def test_all_endpoints_documented(self):
        endpoints = [
            "GET /blackout-api/v1/users",
            "POST /blackout-api/v1/users",
            "PATCH /blackout-api/v1/users/{username}",
            "DELETE /blackout-api/v1/users/{username}",
            "POST /blackout-api/v1/users/{username}/lock",
            "POST /blackout-api/v1/users/{username}/unlock",
            "GET /blackout-api/v1/users/{username}/links",
            "GET /blackout-api/v1/users/{username}/traffic",
            "GET /blackout-api/v1/users/online",
            "GET /blackout-api/v1/traffic",
        ]
        for ep in endpoints:
            self.assertIn(ep, self.text, f"Missing endpoint documentation for: {ep}")

    def test_all_error_codes_documented(self):
        codes = [
            "invalid_request",
            "not_found",
            "conflict",
            "backend_error",
            "request_too_large",
            "unauthorized",
            "method_not_allowed",
        ]
        for code in codes:
            self.assertIn(f"`{code}`", self.text, f"Missing documentation for error code: {code}")

    def test_core_data_models_documented(self):
        models = ["User Object", "Connection Link Object", "Traffic Stats Object", "Online User Object"]
        for model in models:
            self.assertIn(model, self.text, f"Missing documentation for model: {model}")

    def test_review_focus_items_documented(self):
        self.assertIn("204 No Content", self.text)
        self.assertIn("sample", self.text)
        self.assertIn("1 <= sample <= 30", self.text)
        self.assertIn("never", self.text)
        self.assertIn("serialized", self.text.lower())
        self.assertIn("minutes are not supported", self.text.lower())


if __name__ == "__main__":
    unittest.main()
