# API Traffic Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose live Xray per-user and total traffic counters via `GET /blackout-api/v1/traffic` and `GET /blackout-api/v1/users/{username}/traffic`.

**Architecture:** `lib/users.sh` provides `bo_user_traffic_row` to read a user's live uplink, downlink, and total bytes from Xray's `StatsService`. `lib/api.sh` adds the `traffic` adapter command (for all users plus aggregate totals, or a single user), and `api/blackout_api.py` routes the two read-only HTTP `GET` endpoints to the adapter without acquiring `mutation_lock`.

**Tech Stack:** Bash 5, SQLite 3, Xray `statsquery` API, Python 3 (`http.server`, `unittest`)

**Spec:** `docs/superpowers/specs/2026-11-09-api-traffic-usage-design.md`

## Global Constraints

- Reuse existing Xray `StatsService` helpers (`bo_xray_user_stats` and `bo_user_stat_value`) and existing API response conventions (`{"ok":true,"data":...}`).
- Counter fields use `uplink_bytes`, `downlink_bytes`, and `total_bytes` (`uplink_bytes + downlink_bytes`).
- All users registered in SQLite (`bo_db_users_rows`, ordered by `username`) are included in `GET /blackout-api/v1/traffic`, defaulting to `0` when Xray has no counter for a user.
- Read-only traffic endpoints do not acquire the process-wide `mutation_lock`.
- Usernames in `/users/{username}/traffic` must exist in SQLite (`bo_db_user_get`) or return HTTP `404` (`not_found`).

## Review Focus

- Empty user database on `GET /blackout-api/v1/traffic`: returns `total` with `0` for `uplink_bytes`, `downlink_bytes`, and `total_bytes`, and `"users":[]`.
- User with no Xray stat entries (`{"stat":[]}`): defaults `uplink_bytes`, `downlink_bytes`, and `total_bytes` to `0`.
- Unknown username on `GET /blackout-api/v1/users/{username}/traffic`: returns adapter exit `11` (`not_found`, HTTP `404`) rather than `0` bytes.
- Xray stats failure (`bo_xray_user_stats` non-zero exit): returns adapter exit `20` (`backend_error`, HTTP `500`) instead of `0` bytes.
- Extra arguments to `bo_api_cmd traffic`: returns adapter exit `10` (`invalid_request`, HTTP `400`).

---

### Task 1: Add Traffic Adapter Command

**Files:**
- Modify: `lib/users.sh:316-320`
- Modify: `lib/api.sh:510-526`
- Test: `tests/test_api_adapter.sh`

**Interfaces:**
- Consumes: `bo_xray_user_stats(username)` (`lib/xray.sh`), `bo_user_stat_value(stats, username, direction)` (`lib/users.sh`), `bo_db_users_rows()` (`lib/db.sh`), `bo_api_user_row_or_404(username)` (`lib/api.sh`)
- Produces:
  - `bo_user_traffic_row <username>` -> prints `<username>\t<uplink_bytes>\t<downlink_bytes>\t<total_bytes>` to stdout; returns `1` if `bo_xray_user_stats` fails.
  - `bo_api_cmd traffic` -> prints `{"ok":true,"data":{"total":{"uplink_bytes":N,"downlink_bytes":N,"total_bytes":N},"users":[{"username":"...","uplink_bytes":N,"downlink_bytes":N,"total_bytes":N}]}}`.
  - `bo_api_cmd traffic <username>` -> prints `{"ok":true,"data":{"username":"...","uplink_bytes":N,"downlink_bytes":N,"total_bytes":N}}` or exits `11` (`not_found`) / `20` (`backend_error`).

- [ ] **Step 1: Write the failing adapter tests in `tests/test_api_adapter.sh`**

In `tests/test_api_adapter.sh`, update `bo_xray_user_stats` to support an idle user (`idleuser`) returning `{"stat":[]}`, and add assertions for empty DB traffic, single-user traffic, multi-user + idle-user traffic aggregation, unknown user `404`, extra-arg `400`, and stats failure `500`:

```bash
# Inside bo_xray_user_stats() in tests/test_api_adapter.sh, before theonline counter logic:
  if [ "$username" = idleuser ]; then
    printf '{"stat":[]}\n'
    return 0
  fi

# Before `out="$(bo_api_cmd create aiman 1d)"`:
out="$(bo_api_cmd traffic)"
[ "$(printf '%s\n' "$out" | json_get ok)" = True ]
[ "$(printf '%s\n' "$out" | json_get data.total.uplink_bytes)" = 0 ]
[ "$(printf '%s\n' "$out" | json_get data.total.downlink_bytes)" = 0 ]
[ "$(printf '%s\n' "$out" | json_get data.total.total_bytes)" = 0 ]
[ "$(printf '%s\n' "$out" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["data"]["users"]))')" = 0 ]

# After `out="$(bo_api_cmd online 0)"`:
rm -f "$BLACKOUT_TEST_ONLINE_COUNTER"
out="$(bo_api_cmd traffic aiman)"
[ "$(printf '%s\n' "$out" | json_get data.username)" = aiman ]
[ "$(printf '%s\n' "$out" | json_get data.uplink_bytes)" = 1024 ]
[ "$(printf '%s\n' "$out" | json_get data.downlink_bytes)" = 2048 ]
[ "$(printf '%s\n' "$out" | json_get data.total_bytes)" = 3072 ]

bo_api_cmd create idleuser 1d >/dev/null
rm -f "$BLACKOUT_TEST_ONLINE_COUNTER"
out="$(bo_api_cmd traffic)"
[ "$(printf '%s\n' "$out" | json_get data.total.uplink_bytes)" = 1024 ]
[ "$(printf '%s\n' "$out" | json_get data.total.downlink_bytes)" = 2048 ]
[ "$(printf '%s\n' "$out" | json_get data.total.total_bytes)" = 3072 ]
[ "$(printf '%s\n' "$out" | json_get data.users.0.username)" = aiman ]
[ "$(printf '%s\n' "$out" | json_get data.users.0.total_bytes)" = 3072 ]
[ "$(printf '%s\n' "$out" | json_get data.users.1.username)" = idleuser ]
[ "$(printf '%s\n' "$out" | json_get data.users.1.uplink_bytes)" = 0 ]
[ "$(printf '%s\n' "$out" | json_get data.users.1.downlink_bytes)" = 0 ]
[ "$(printf '%s\n' "$out" | json_get data.users.1.total_bytes)" = 0 ]
bo_api_cmd remove idleuser >/dev/null

out="$(expect_status 11 bo_api_cmd traffic ghost)"
[ "$(printf '%s\n' "$out" | json_get error.code)" = not_found ]

out="$(expect_status 10 bo_api_cmd traffic aiman extra)"
[ "$(printf '%s\n' "$out" | json_get error.code)" = invalid_request ]

BLACKOUT_TEST_STATS_FAIL=1
out="$(expect_status 20 bo_api_cmd traffic)"
[ "$(printf '%s\n' "$out" | json_get error.code)" = backend_error ]
out="$(expect_status 20 bo_api_cmd traffic aiman)"
[ "$(printf '%s\n' "$out" | json_get error.code)" = backend_error ]
unset BLACKOUT_TEST_STATS_FAIL
```

- [ ] **Step 2: Run the adapter test to verify it fails**

Run: `bash tests/test_api_adapter.sh`
Expected: FAIL with exit status `10` (`unknown api command`) on `bo_api_cmd traffic`.

- [ ] **Step 3: Implement `bo_user_traffic_row` in `lib/users.sh` and `bo_api_traffic` in `lib/api.sh`**

In `lib/users.sh`, right after `bo_user_stat_value`, add `bo_user_traffic_row(username)` that calls `bo_xray_user_stats "$username"`, extracts `uplink` and `downlink` via `bo_user_stat_value`, normalizes both with `$((value + 0))`, and prints `username\tuplink\tdownlink\ttotal`.

In `lib/api.sh`, add `bo_api_traffic` and wire `traffic) bo_api_traffic "$@" ;;` in `bo_api_cmd`:
- When `username` argument is provided: validate no extra args (`bo_api_need_no_extra`), verify user exists via `bo_api_user_row_or_404 "$username"`, read `bo_user_traffic_row "$username"`, and print `{"ok":true,"data":{"username":...,"uplink_bytes":...,"downlink_bytes":...,"total_bytes":...}}`.
- When no arguments are provided: read `bo_db_users_rows` (returning `BO_API_BACKEND` on failure), call `bo_user_traffic_row` for each user (returning `BO_API_BACKEND` on failure), sum `total_uplink`, `total_downlink`, and `total_bytes`, and print `{"ok":true,"data":{"total":{...},"users":[...]}}`.

- [ ] **Step 4: Run the adapter test to verify it passes**

Run: `bash tests/test_api_adapter.sh && bash -n lib/users.sh lib/api.sh tests/test_api_adapter.sh`
Expected: PASS with no output.

- [ ] **Step 5: Commit adapter traffic support**

```bash
git -c user.name="Aiman Amir" -c user.email="aiman@148943.xyz" add lib/users.sh lib/api.sh tests/test_api_adapter.sh
git -c user.name="Aiman Amir" -c user.email="aiman@148943.xyz" commit -m "feat: add traffic command to api adapter"
```

### Task 2: Expose HTTP Traffic Routes and Documentation

**Files:**
- Modify: `api/blackout_api.py:192-210`
- Modify: `tests/test_api_http.py:50-75,200-250`
- Modify: `docs/api.md:67-135`

**Interfaces:**
- Consumes: `bo_api_cmd traffic [username]` from Task 1
- Produces:
  - `GET /blackout-api/v1/traffic` -> calls adapter `["traffic"]`
  - `GET /blackout-api/v1/users/{username}/traffic` -> calls adapter `["traffic", username]`

- [ ] **Step 1: Write the failing HTTP route tests in `tests/test_api_http.py`**

Update the fake adapter in `tests/test_api_http.py` to handle `traffic` (returning `404` when `sys.argv[2] == "ghost"`, single-user payload when `len(sys.argv) == 3`, and `{"total": ..., "users": [...]}` when `len(sys.argv) == 2`), and add assertions in `test_maps_adapter_conflict_not_found_and_backend_statuses` and `test_lock_unlock_links_and_online_routes`:

```python
# In setUp() fake adapter:
if cmd in {"modify", "remove", "lock", "unlock", "links", "traffic"} and len(sys.argv) > 2 and sys.argv[2] == "ghost":
    print(json.dumps({"ok": False, "error": {"code": "not_found", "message": "missing"}}))
    sys.exit(11)
...
elif cmd == "traffic" and len(sys.argv) == 2:
    payload = {
        "total": {"uplink_bytes": 1024, "downlink_bytes": 2048, "total_bytes": 3072},
        "users": [{"username": "aiman", "uplink_bytes": 1024, "downlink_bytes": 2048, "total_bytes": 3072}],
    }
elif cmd == "traffic" and len(sys.argv) == 3:
    payload = {"username": sys.argv[2], "uplink_bytes": 1024, "downlink_bytes": 2048, "total_bytes": 3072}

# In test_maps_adapter_conflict_not_found_and_backend_statuses:
status, payload, _ = self.request("GET", "/blackout-api/v1/users/ghost/traffic")
self.assertEqual(status, 404)
self.assertEqual(payload["error"]["code"], "not_found")

# In test_lock_unlock_links_and_online_routes:
status, payload, _ = self.request("GET", "/blackout-api/v1/traffic")
self.assertEqual(status, 200)
self.assertEqual(payload["data"]["total"]["total_bytes"], 3072)
self.assertEqual(payload["data"]["users"][0]["username"], "aiman")

status, payload, _ = self.request("GET", "/blackout-api/v1/users/aiman/traffic")
self.assertEqual(status, 200)
self.assertEqual(payload["data"]["username"], "aiman")
self.assertEqual(payload["data"]["total_bytes"], 3072)
```

- [ ] **Step 2: Run the HTTP test suite to verify it fails**

Run: `python3 -m unittest tests/test_api_http.py`
Expected: FAIL because `/blackout-api/v1/traffic` and `/blackout-api/v1/users/aiman/traffic` return `404` (`route not found`).

- [ ] **Step 3: Implement `GET` routes in `api/blackout_api.py` and document in `docs/api.md`**

In `BlackoutApiHandler.do_GET` (`api/blackout_api.py`):
- When `parts == ["traffic"]`: call `self.adapter_response(["traffic"])` and return.
- When `len(parts or []) == 3 and parts[0] == "users" and parts[2] == "traffic"`: call `self.adapter_response(["traffic", parts[1]])` and return.

In `docs/api.md`:
- Add `GET /traffic` and `GET /users/{username}/traffic` to the `## Endpoints` list.
- Add `curl` examples for reading all traffic (`$BASE/traffic`) and single-user traffic (`$BASE/users/aiman/traffic`) under `## Examples`.

- [ ] **Step 4: Run HTTP tests and the full test suite**

Run: `python3 -m unittest tests/test_api_http.py && bash tests/run.sh && git diff --check`
Expected: PASS (`tests ok`).

- [ ] **Step 5: Commit HTTP routes and documentation**

```bash
git -c user.name="Aiman Amir" -c user.email="aiman@148943.xyz" add api/blackout_api.py tests/test_api_http.py docs/api.md
git -c user.name="Aiman Amir" -c user.email="aiman@148943.xyz" commit -m "feat: expose traffic endpoints in http api"
```
