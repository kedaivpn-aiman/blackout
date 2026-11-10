# Complete Blackout API Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `docs/api.md` with an exhaustive developer reference for Blackout's HTTP API, accompanied by an automated doc validation test ensuring JSON syntax validity and complete endpoint/error coverage.

**Architecture:** Create `tests/test_docs_api.py` to assert that all 10 endpoints, data models, error codes, and JSON blocks in `docs/api.md` are well-formed and complete. Incrementally author the reference document following Approach 1 (Service & Auth -> Envelopes & Error Catalog -> Data Models -> User Lifecycle -> Client Provisioning -> Metrics & Telemetry) with exact request/response schemas, status codes, and curl snippets.

**Tech Stack:** Markdown (GitHub Flavored Markdown), Python `unittest` & `json` (for doc verification).

**Spec:** `docs/superpowers/specs/2026-11-10-api-reference-design.md`

## Global Constraints

- Must accurately reflect the implementation in `api/blackout_api.py` and `lib/api.sh`.
- Must document all 10 HTTP endpoints under `/blackout-api/v1`.
- All JSON examples in `docs/api.md` must be syntactically valid JSON.
- Every endpoint must specify: HTTP method, path, required headers, request parameters/body, response schema, possible error codes, and a `curl` example.
- Preserves operational setup details (systemd, port 8787, CLI token management) in a compact introductory section.

## Review Focus

- Missing query parameter constraints on `/users/online` (must document integer bounds `1 <= sample <= 30` and default `5`).
- Incorrect HTTP status code for user deletion (must specify `204 No Content` with zero-length body).
- Unclear duration formats on user creation/modification (must document relative durations like `12h`, `7d`, `30d`, `1m` and non-expiring `"never"`).
- Omission of mutation serialization note (document that user mutations run serialized behind an internal lock).
- Discrepancy between single-user traffic format (`{username, uplink_bytes, downlink_bytes, total_bytes}`) and total traffic format (`{total: {...}, users: [...]}`).

---

### Task 1: Create Doc Verification Suite and Global Specifications

**Files:**
- Create: `tests/test_docs_api.py`
- Modify: `docs/api.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-11-10-api-reference-design.md`, `api/blackout_api.py`, `lib/api.sh`
- Produces: `tests/test_docs_api.py` test suite and the top half of `docs/api.md` (Overview, Service, Authentication, Request/Response Envelopes, Error Catalog, Data Models).

- [ ] **Step 1: Write the failing documentation validation test in `tests/test_docs_api.py`**

```python
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
        self.assertIn("30", self.text)
        self.assertIn("never", self.text)
        self.assertIn("serialized", self.text.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_docs_api.py -v`
Expected: FAIL (missing models, full endpoints, error codes).

- [ ] **Step 3: Implement Service Overview, Authentication, Envelopes, Error Catalog, and Models in `docs/api.md`**

Author the first half of `docs/api.md`:
- Title and Introduction: Blackout HTTP User API for external integrations.
- Service Architecture & Base URL: loopback `127.0.0.1:8787`, TLS path `https://<DOMAIN>/blackout-api/v1`, systemd management.
- Authentication: Bearer token in `Authorization: Bearer <TOKEN>`, token rotation and retrieval CLI commands.
- Request & Response Conventions: JSON encoding, `Content-Type: application/json`, max body 64 KB, serialized user mutations.
- Envelopes: Success format `{"ok": true, "data": ...}`, error format `{"ok": false, "error": {"code": "...", "message": "..."}}`.
- Error Catalog: Table mapping error code, HTTP status, and description for all 7 error codes.
- Core Data Models: Tables and JSON schemas for `User Object`, `Connection Link Object`, `Traffic Stats Object`, `Online User Object`.

- [ ] **Step 4: Run test to verify partial progress**

Run: `python3 -m unittest tests/test_docs_api.py -v`
Expected: `test_all_error_codes_documented` and `test_core_data_models_documented` PASS; endpoint checks pending.

- [ ] **Step 5: Commit**

```bash
git add tests/test_docs_api.py docs/api.md
git commit -m "docs: add api test and global conventions to api reference"
```

---

### Task 2: Document User Lifecycle Endpoints

**Files:**
- Modify: `docs/api.md`
- Test: `tests/test_docs_api.py`

**Interfaces:**
- Consumes: Task 1 conventions and data models
- Produces: Detailed documentation for:
  - `GET /blackout-api/v1/users`
  - `POST /blackout-api/v1/users`
  - `PATCH /blackout-api/v1/users/{username}`
  - `DELETE /blackout-api/v1/users/{username}`
  - `POST /blackout-api/v1/users/{username}/lock`
  - `POST /blackout-api/v1/users/{username}/unlock`

- [ ] **Step 1: Check existing test status**

Run: `python3 -m unittest tests/test_docs_api.py -v`
Expected: FAIL on `test_all_endpoints_documented`.

- [ ] **Step 2: Implement User Lifecycle endpoints section in `docs/api.md`**

For each endpoint, include:
- Endpoint heading, description, and HTTP method/path (`METHOD /blackout-api/v1/...`).
- Request headers.
- Path parameters (e.g. `{username}` alphanumeric).
- Request body schema (for `POST /users` and `PATCH /users/{username}`) detailing field name, type, required status, format/durations (`12h`, `7d`, `30d`, `1m`, `never`), and example.
- Successful response status code (`200 OK`, `201 Created`, `204 No Content`) with complete JSON payload example.
- Error responses: exact status codes (400, 401, 404, 409, 500) and error payloads.
- Working `curl` snippet.

- [ ] **Step 3: Run test to verify progress**

Run: `python3 -m unittest tests/test_docs_api.py -v`
Expected: Progress toward all endpoints passing.

- [ ] **Step 4: Commit**

```bash
git add docs/api.md
git commit -m "docs: add user lifecycle endpoints to api reference"
```

---

### Task 3: Document Client Provisioning and Metrics Endpoints & Full Verification

**Files:**
- Modify: `docs/api.md`
- Test: `tests/test_docs_api.py`

**Interfaces:**
- Consumes: Task 1 & Task 2
- Produces: Detailed documentation for:
  - `GET /blackout-api/v1/users/{username}/links`
  - `GET /blackout-api/v1/users/{username}/traffic`
  - `GET /blackout-api/v1/traffic`
  - `GET /blackout-api/v1/users/online`

- [ ] **Step 1: Implement Client Provisioning and Metrics sections in `docs/api.md`**

Document:
- `GET /blackout-api/v1/users/{username}/links`: path param `{username}`, 200 response with array of `{"name": "...", "link": "vless://..."}`, 404 if user not found, curl example.
- `GET /blackout-api/v1/users/{username}/traffic`: path param `{username}`, 200 response with single user traffic object, 404 if user not found, curl example.
- `GET /blackout-api/v1/traffic`: 200 response with total uplink/downlink/total bytes and user list breakdown, curl example.
- `GET /blackout-api/v1/users/online`: query parameter `sample` (optional integer from 1 to 30, default 5), 400 error if sample outside range, 200 response with array of active users and delta/total bytes, curl example.

- [ ] **Step 2: Run documentation test to verify 100% pass**

Run: `python3 -m unittest tests/test_docs_api.py -v`
Expected: Ran 5 tests in 0.05s - OK.

- [ ] **Step 3: Run integration test suites to confirm no regressions**

Run:
- `python3 -m unittest tests/test_api_http.py` (Expected: OK)
- `bash tests/test_api_adapter.sh` (Expected: OK)

- [ ] **Step 4: Commit**

```bash
git add docs/api.md
git commit -m "docs: complete api reference and pass doc validation tests"
```
