# Blackout User API Reference

The Blackout User API is a local HTTP service providing programmatic user management for external integrations, web panels, Telegram bots, and client provisioning tools.

The API exclusively manages proxy users, subscription links, and traffic metrics. Infrastructure operations (SSL/TLS certificates, Xray core updates, domain routing, and system updates) remain restricted to the `blackout` CLI.

---

## Service Architecture & Administration

### Base URL & Network Binding

The API service binds exclusively to the local loopback interface:

```text
127.0.0.1:8787
```

In production deployments, Nginx terminates TLS and reverse-proxies requests under the prefix `/blackout-api/v1`:

```text
https://<YOUR_DOMAIN>/blackout-api/v1
```

All route paths documented in this reference are prefixed with `/blackout-api/v1`.

### Service Management

The API is managed by systemd under the `blackout-api` unit:

```bash
systemctl status blackout-api
journalctl -u blackout-api -n 100 --no-pager
```

By default on fresh installations, the API is disabled. Manage the service state using the Blackout CLI:

```bash
# Enable and start the service
blackout api enable

# Disable and stop the service
blackout api disable

# Check service status
blackout api status
```

---

## Authentication

Every request to the API requires HTTP Bearer token authentication via the standard `Authorization` header:

```http
Authorization: Bearer <TOKEN>
```

Requests omitting or supplying an invalid token immediately receive an HTTP `401 Unauthorized` response.

### Reading and Rotating API Tokens

The API token is securely generated and stored in `/etc/blackout/blackout.env` with strict file permissions (`0600`):

```bash
# Read active token (root required)
. /etc/blackout/blackout.env
printf '%s\n' "$BLACKOUT_API_TOKEN"
```

To rotate the token and revoke the previous secret:

```bash
blackout api token
```

Rotating the token restarts the `blackout-api` service automatically. Any panels or integrations must be updated with the newly generated token.

---

## Request & Response Conventions

- **Content Negotiation:** All requests with payloads must specify `Content-Type: application/json`.
- **Payload Limits:** Maximum request body size is 64 KB (65,536 bytes). Requests exceeding this limit return `413 Payload Too Large` with error code `request_too_large`.
- **Concurrency & Concurrency Locking:** User mutations (`POST`, `PATCH`, `DELETE`, lock, unlock) are serialized internally using a synchronization lock to prevent SQLite and Xray state race conditions.
- **Duration Syntax:** User expiration durations accept positive integer values combined with a unit identifier or the literal string `"never"`:
  - `h`: Hours (e.g. `12h` = 43,200 seconds).
  - `d`: Days (e.g. `7d`, `30d` = 86,400 seconds per day).
  - `m`: Months (defined as 30-day periods, e.g. `1m` = 2,592,000 seconds). *Note: Minutes are not supported.*
  - `"never"`: Non-expiring account (sets `expires_at` to the sentinel epoch `4102444800`, year 2100).

### Standard Response Envelope

Successful requests return HTTP status codes `200 OK` or `201 Created` with a standard JSON envelope:

```json
{
  "ok": true,
  "data": {}
}
```

Successful deletion (`DELETE /blackout-api/v1/users/{username}`) returns `204 No Content` with an empty response body.

### Standard Error Envelope

When a request fails, the API responds with an HTTP status code matching the failure class and a structured JSON error envelope:

```json
{
  "ok": false,
  "error": {
    "code": "invalid_request",
    "message": "username and duration are required"
  }
}
```

---

## Error Catalog

The API maps error conditions to predictable machine-readable error codes and corresponding HTTP status codes:

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `invalid_request` | `400 Bad Request` | Missing required parameters, invalid JSON, or invalid values (e.g. non-positive duration or sample outside 1-30). |
| `unauthorized` | `401 Unauthorized` | Missing or invalid `Authorization: Bearer <TOKEN>` header. |
| `not_found` | `404 Not Found` | Target user or requested route was not found. |
| `method_not_allowed` | `405 Method Not Allowed` | HTTP method not permitted on the targeted resource endpoint. |
| `conflict` | `409 Conflict` | Target resource already exists (e.g. attempting to create an existing username). |
| `request_too_large` | `413 Payload Too Large` | Request body exceeds the 64 KB size limit. |
| `backend_error` | `500 Internal Server Error` | Database error, Xray API communication failure, adapter failure, or command timeout. |

---

## Core Data Models

### User Object

Represents a provisioned proxy account on Blackout.

| Field | Type | Description |
|-------|------|-------------|
| `username` | string | Unique user identifier (alphanumeric). |
| `uuid` | string | UUIDv4 assigned to the client for Xray authentication. |
| `level` | integer | Privilege level (default `0`). |
| `status` | string | User account status: `"active"`, `"locked"`, or `"expired"`. |
| `created_at` | integer | Unix timestamp (seconds) when user was created. |
| `expires_at` | integer | Unix timestamp (seconds) when access expires. |
| `updated_at` | integer | Unix timestamp (seconds) when user record was last modified. |

```json
{
  "username": "aiman",
  "uuid": "4f9b8608-8e7c-48c9-83bc-69ff15bfbaec",
  "level": 0,
  "status": "active",
  "created_at": 1700000000,
  "expires_at": 1702592000,
  "updated_at": 1700000000
}
```

### Connection Link Object

Represents an individual proxy client configuration URI and friendly label.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable configuration name (e.g. `"VLESS WS TLS"`). |
| `link` | string | Complete URI string importable into proxy clients (e.g. v2rayN, Shadowrocket, Sing-box). |

```json
{
  "name": "VLESS WS TLS",
  "link": "vless://4f9b8608-8e7c-48c9-83bc-69ff15bfbaec@example.com:443?type=ws&security=tls&path=%2Fblackout-ws#aiman-VLESS-WS-TLS"
}
```

### Traffic Stats Object

Represents network byte counts for a specific user or global server traffic.

Single-user traffic object:

| Field | Type | Description |
|-------|------|-------------|
| `username` | string | Target username identifier. |
| `uplink_bytes` | integer | Bytes uploaded by the client. |
| `downlink_bytes` | integer | Bytes downloaded by the client. |
| `total_bytes` | integer | Combined sum of uplink and downlink bytes. |

```json
{
  "username": "aiman",
  "uplink_bytes": 1048576,
  "downlink_bytes": 5242880,
  "total_bytes": 6291456
}
```

Global traffic object:

```json
{
  "total": {
    "uplink_bytes": 10485760,
    "downlink_bytes": 52428800,
    "total_bytes": 62914560
  },
  "users": [
    {
      "username": "aiman",
      "uplink_bytes": 1048576,
      "downlink_bytes": 5242880,
      "total_bytes": 6291456
    }
  ]
}
```

### Online User Object

Represents an active client observed during a traffic sampling window.

| Field | Type | Description |
|-------|------|-------------|
| `username` | string | Username observed sending or receiving traffic. |
| `delta_bytes` | integer | Number of bytes transferred during the observation sample window. |
| `total_bytes` | integer | Total lifetime bytes transferred by this user. |

```json
{
  "username": "aiman",
  "delta_bytes": 10240,
  "total_bytes": 6291456
}
```

---

## User Lifecycle Endpoints

### List All Users

`GET /blackout-api/v1/users`

Retrieves a list of all provisioned proxy users along with their statuses and timestamps.

- **Headers:**
  - `Authorization: Bearer <TOKEN>`
- **Request Body:** None
- **Response:** `200 OK`

```json
{
  "ok": true,
  "data": [
    {
      "username": "aiman",
      "uuid": "4f9b8608-8e7c-48c9-83bc-69ff15bfbaec",
      "level": 0,
      "status": "active",
      "created_at": 1700000000,
      "expires_at": 1702592000,
      "updated_at": 1700000000
    }
  ]
}
```

- **Error Codes:** `unauthorized` (401), `backend_error` (500).

```bash
curl -sS -H "Authorization: Bearer $BLACKOUT_API_TOKEN" \
  https://$DOMAIN/blackout-api/v1/users
```

---

### Create User

`POST /blackout-api/v1/users`

Provisions a new user account, assigns a fresh UUID, calculates expiry, and activates the user in the running Xray instance.

- **Headers:**
  - `Authorization: Bearer <TOKEN>`
  - `Content-Type: application/json`
- **Request Body:**
  | Field | Type | Required | Description |
  |-------|------|----------|-------------|
  | `username` | string | Yes | Unique alphanumeric username. |
  | `duration` | string | Yes | Relative duration (e.g. `12h`, `7d`, `30d`, `1m`) or `"never"`. |

```json
{
  "username": "aiman",
  "duration": "30d"
}
```

- **Response:** `201 Created`

```json
{
  "ok": true,
  "data": {
    "username": "aiman",
    "uuid": "4f9b8608-8e7c-48c9-83bc-69ff15bfbaec",
    "level": 0,
    "status": "active",
    "created_at": 1700000000,
    "expires_at": 1702592000,
    "updated_at": 1700000000
  }
}
```

- **Error Codes:** `invalid_request` (400), `unauthorized` (401), `conflict` (409), `request_too_large` (413), `backend_error` (500).

```bash
curl -sS -X POST https://$DOMAIN/blackout-api/v1/users \
  -H "Authorization: Bearer $BLACKOUT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"aiman","duration":"30d"}'
```

---

### Modify User Duration

`PATCH /blackout-api/v1/users/{username}`

Modifies the active access duration and recalculates the expiration timestamp for an existing user.

- **Headers:**
  - `Authorization: Bearer <TOKEN>`
  - `Content-Type: application/json`
- **Path Parameters:**
  - `username` (string, required): Alphanumeric username of the target account.
- **Request Body:**
  | Field | Type | Required | Description |
  |-------|------|----------|-------------|
  | `duration` | string | Yes | Relative duration (e.g. `12h`, `7d`, `30d`, `1m`) or `"never"`. |

```json
{
  "duration": "7d"
}
```

- **Response:** `200 OK`

```json
{
  "ok": true,
  "data": {
    "username": "aiman",
    "uuid": "4f9b8608-8e7c-48c9-83bc-69ff15bfbaec",
    "level": 0,
    "status": "active",
    "created_at": 1700000000,
    "expires_at": 1700604800,
    "updated_at": 1700003600
  }
}
```

- **Error Codes:** `invalid_request` (400), `unauthorized` (401), `not_found` (404), `request_too_large` (413), `backend_error` (500).

```bash
curl -sS -X PATCH https://$DOMAIN/blackout-api/v1/users/aiman \
  -H "Authorization: Bearer $BLACKOUT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"duration":"7d"}'
```

---

### Delete User

`DELETE /blackout-api/v1/users/{username}`

Deletes a user account, removes proxy credentials from the Xray core, and purges the user from the database.

- **Headers:**
  - `Authorization: Bearer <TOKEN>`
- **Path Parameters:**
  - `username` (string, required): Alphanumeric username of target account.
- **Request Body:** None
- **Response:** `204 No Content` (empty body)
- **Error Codes:** `unauthorized` (401), `not_found` (404), `backend_error` (500).

```bash
curl -sS -X DELETE https://$DOMAIN/blackout-api/v1/users/aiman \
  -H "Authorization: Bearer $BLACKOUT_API_TOKEN"
```

---

### Lock User

`POST /blackout-api/v1/users/{username}/lock`

Suspends a user's proxy access immediately by removing credentials from the Xray core while setting their status to `"locked"`.

- **Headers:**
  - `Authorization: Bearer <TOKEN>`
- **Path Parameters:**
  - `username` (string, required): Target user to lock.
- **Request Body:** None
- **Response:** `200 OK`

```json
{
  "ok": true,
  "data": {
    "username": "aiman",
    "uuid": "4f9b8608-8e7c-48c9-83bc-69ff15bfbaec",
    "level": 0,
    "status": "locked",
    "created_at": 1700000000,
    "expires_at": 1702592000,
    "updated_at": 1700005000
  }
}
```

- **Error Codes:** `unauthorized` (401), `not_found` (404), `backend_error` (500).

```bash
curl -sS -X POST https://$DOMAIN/blackout-api/v1/users/aiman/lock \
  -H "Authorization: Bearer $BLACKOUT_API_TOKEN"
```

---

### Unlock User

`POST /blackout-api/v1/users/{username}/unlock`

Restores proxy access for a previously locked user by injecting their credentials back into Xray core and updating their status to `"active"`.

- **Headers:**
  - `Authorization: Bearer <TOKEN>`
- **Path Parameters:**
  - `username` (string, required): Target user to unlock.
- **Request Body:** None
- **Response:** `200 OK`

```json
{
  "ok": true,
  "data": {
    "username": "aiman",
    "uuid": "4f9b8608-8e7c-48c9-83bc-69ff15bfbaec",
    "level": 0,
    "status": "active",
    "created_at": 1700000000,
    "expires_at": 1702592000,
    "updated_at": 1700006000
  }
}
```

- **Error Codes:** `unauthorized` (401), `not_found` (404), `backend_error` (500).

```bash
curl -sS -X POST https://$DOMAIN/blackout-api/v1/users/aiman/unlock \
  -H "Authorization: Bearer $BLACKOUT_API_TOKEN"
```

---

## Client Provisioning Endpoints

### Get Client Connection Links

`GET /blackout-api/v1/users/{username}/links`

Generates ready-to-import client proxy configurations (such as VLESS over WebSocket with TLS) for a specific user.

- **Headers:**
  - `Authorization: Bearer <TOKEN>`
- **Path Parameters:**
  - `username` (string, required): Target user to generate links for.
- **Request Body:** None
- **Response:** `200 OK`

```json
{
  "ok": true,
  "data": [
    {
      "name": "VLESS WS TLS",
      "link": "vless://4f9b8608-8e7c-48c9-83bc-69ff15bfbaec@example.com:443?type=ws&security=tls&path=%2Fblackout-ws#aiman-VLESS-WS-TLS"
    }
  ]
}
```

- **Error Codes:** `unauthorized` (401), `not_found` (404), `backend_error` (500).

```bash
curl -sS -H "Authorization: Bearer $BLACKOUT_API_TOKEN" \
  https://$DOMAIN/blackout-api/v1/users/aiman/links
```

---

## Metrics & Observability Endpoints

### Get User Traffic Usage

`GET /blackout-api/v1/users/{username}/traffic`

Queries cumulative byte counters (uplink, downlink, total) consumed by a specific user.

- **Headers:**
  - `Authorization: Bearer <TOKEN>`
- **Path Parameters:**
  - `username` (string, required): Target user to retrieve traffic for.
- **Request Body:** None
- **Response:** `200 OK`

```json
{
  "ok": true,
  "data": {
    "username": "aiman",
    "uplink_bytes": 1048576,
    "downlink_bytes": 5242880,
    "total_bytes": 6291456
  }
}
```

- **Error Codes:** `unauthorized` (401), `not_found` (404), `backend_error` (500).

```bash
curl -sS -H "Authorization: Bearer $BLACKOUT_API_TOKEN" \
  https://$DOMAIN/blackout-api/v1/users/aiman/traffic
```

---

### Get Global Traffic Usage

`GET /blackout-api/v1/traffic`

Retrieves global server traffic sums and a detailed per-user traffic usage breakdown. Note that unlike the single-user endpoint which returns a flat statistics object, the global endpoint encapsulates aggregate counters in a `total` object alongside a `users` array.

- **Headers:**
  - `Authorization: Bearer <TOKEN>`
- **Request Body:** None
- **Response:** `200 OK`

```json
{
  "ok": true,
  "data": {
    "total": {
      "uplink_bytes": 10485760,
      "downlink_bytes": 52428800,
      "total_bytes": 62914560
    },
    "users": [
      {
        "username": "aiman",
        "uplink_bytes": 1048576,
        "downlink_bytes": 5242880,
        "total_bytes": 6291456
      }
    ]
  }
}
```

- **Error Codes:** `unauthorized` (401), `backend_error` (500).

```bash
curl -sS -H "Authorization: Bearer $BLACKOUT_API_TOKEN" \
  https://$DOMAIN/blackout-api/v1/traffic
```

---

### Get Online Users

`GET /blackout-api/v1/users/online`

Samples active client traffic over an observation window to identify clients currently connected and streaming data through Xray.

- **Headers:**
  - `Authorization: Bearer <TOKEN>`
- **Query Parameters:**
  | Parameter | Type | Required | Default | Description |
  |-----------|------|----------|---------|-------------|
  | `sample` | integer | No | `5` | Sampling window duration in seconds. Must be an integer between 1 and 30 (`1 <= sample <= 30`). |

- **Request Body:** None
- **Response:** `200 OK`

```json
{
  "ok": true,
  "data": [
    {
      "username": "aiman",
      "delta_bytes": 10240,
      "total_bytes": 6291456
    }
  ]
}
```

- **Error Codes:** `invalid_request` (400) if `sample` is not an integer or outside the 1–30 range, `unauthorized` (401), `backend_error` (500).

```bash
curl -sS -H "Authorization: Bearer $BLACKOUT_API_TOKEN" \
  "https://$DOMAIN/blackout-api/v1/users/online?sample=5"
```
