# API Traffic Usage Design

## Intent and Why

Expose live per-user and total traffic counters in the Blackout HTTP API so external tools and dashboards can read current bandwidth usage for each user and the server total without scraping CLI output or modifying SQLite state.

## Goals, Non-Goals, and Anti-Goals

- **Goals:**
  - Provide `GET /blackout-api/v1/traffic` returning all users' live traffic counters (`uplink_bytes`, `downlink_bytes`, `total_bytes`) and the aggregate `total` across all users.
  - Provide `GET /blackout-api/v1/users/{username}/traffic` returning a single user's live traffic counters (`username`, `uplink_bytes`, `downlink_bytes`, `total_bytes`) or `404` when the user does not exist in SQLite.
  - Reuse existing Xray `StatsService` helpers (`bo_xray_user_stats` and `bo_user_stat_value`) and existing API response conventions (`{"ok":true,"data":...}`).
- **Non-Goals:**
  - Persisting historical counters in SQLite (`traffic_snapshots`) or surviving Xray restarts.
  - Traffic quota enforcement or resetting Xray counters (`--reset=false` remains unchanged).
- **Anti-Goals:**
  - Breaking existing `GET /blackout-api/v1/users` response structure or coupling user-list health checks (`bo_status_user_api`) to live Xray stats queries.

## Constraints

- Must use the existing Python stdlib HTTP server (`api/blackout_api.py`) and non-interactive Bash adapter (`lib/api.sh`).
- Every request remains gated by `Authorization: Bearer <BLACKOUT_API_TOKEN>`.
- Read-only traffic endpoints do not acquire the process-wide `mutation_lock`.
- Usernames in `/users/{username}/traffic` must exist in SQLite (`bo_db_user_get`) or return HTTP `404` (`not_found`), matching `links`, `lock`, `unlock`, `modify`, and `remove`.

## Approaches

### 1. Dedicated traffic endpoints (Selected)
Add `GET /blackout-api/v1/traffic` (all users + aggregate total) and `GET /blackout-api/v1/users/{username}/traffic` (single user).
- **Trade-offs:** Returns both per-user counters and the server total in one call while keeping `GET /blackout-api/v1/users` fast, SQLite-only, and backward-compatible. Callers wanting both user metadata (`expires_at`, `status`) and traffic either call both endpoints or join by `username`.
- **Why selected:** Directly satisfies reading all per-user traffic and total traffic in a single response without breaking `GET /blackout-api/v1/users` or slowing down status checks.

### 2. Embed per-user traffic in `GET /blackout-api/v1/users` plus a separate total endpoint
Add `uplink_bytes`, `downlink_bytes`, and `total_bytes` to each item in `GET /blackout-api/v1/users` and add a separate endpoint for total traffic.
- **Trade-offs:** Combines user metadata and usage in `GET /users`, but still requires a second endpoint for total traffic (since `GET /users` returns `data` as a JSON array) and makes every `GET /users` request (including `bo_status_user_api`) depend on live Xray `statsquery` calls.

## Decided Design

### HTTP Routes (`api/blackout_api.py`)

- `GET /blackout-api/v1/traffic` -> invokes adapter `["traffic"]`.
- `GET /blackout-api/v1/users/{username}/traffic` -> invokes adapter `["traffic", username]`.

### Adapter Behavior (`lib/api.sh` and `lib/users.sh`)

- **Proposed calls (designer defaults):**
  - Counter fields use `uplink_bytes`, `downlink_bytes`, and `total_bytes` (`uplink_bytes + downlink_bytes`), matching `bo_api_online`.
  - All users registered in SQLite (`bo_db_users_rows`, ordered by `username`) are included in `GET /blackout-api/v1/traffic`, even if `locked`, `expired`, or idle. When Xray has no counter for a user, counters default to `0`.
  - `total` in `GET /blackout-api/v1/traffic` is the sum of `uplink_bytes`, `downlink_bytes`, and `total_bytes` across all users.
  - If querying SQLite or `bo_xray_user_stats` fails, the adapter exits with `BO_API_BACKEND` (`20`), which maps to HTTP `500` (`backend_error`).

#### `GET /blackout-api/v1/traffic` Response

```json
{
  "ok": true,
  "data": {
    "total": {
      "uplink_bytes": 1024,
      "downlink_bytes": 2048,
      "total_bytes": 3072
    },
    "users": [
      {
        "username": "aiman",
        "uplink_bytes": 1024,
        "downlink_bytes": 2048,
        "total_bytes": 3072
      }
    ]
  }
}
```

#### `GET /blackout-api/v1/users/{username}/traffic` Response

```json
{
  "ok": true,
  "data": {
    "username": "aiman",
    "uplink_bytes": 1024,
    "downlink_bytes": 2048,
    "total_bytes": 3072
  }
}
```

## Left to the Builder

- Exact helper function names in `lib/users.sh` and `lib/api.sh` (e.g., `bo_user_traffic_row` / `bo_user_traffic_rows` and `bo_api_traffic`).
- Updating `docs/api.md` with the new endpoints and `curl` examples.
- Extending unit/integration tests in `tests/test_api_adapter.sh` and `tests/test_api_http.py`.
