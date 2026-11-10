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
- **Duration Syntax:** User expiration durations accept human-readable relative units (`12h`, `7d`, `30d`, `1m`) or the literal string `"never"` for non-expiring accounts.

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

## API Endpoints

Wait, to keep tests in partial progress, we don't have all detailed endpoint sections yet.
Wait, let's see what Step 4 expects:
"Run: `python3 -m unittest tests/test_docs_api.py -v`
Expected: `test_all_error_codes_documented` and `test_core_data_models_documented` PASS; endpoint checks pending."

Let's test this right now.
