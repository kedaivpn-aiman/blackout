# Design Doc: Complete Blackout User API Reference

- **Date:** 2026-11-10
- **Topic:** Complete Developer API Reference
- **Target File:** `docs/api.md`

## Intent and Why
Provide external developers building web panels, Telegram bots, client applications, and automation systems with an exhaustive, production-grade API reference for Blackout's local HTTP API. The current `docs/api.md` is a brief operational overview; this document replaces it with a complete contract specification.

## Goals
- Replace `docs/api.md` with a complete reference covering all 10 API endpoints across User Lifecycle, Client Configuration, and Metrics & Observability.
- Fully document authentication (`Bearer <TOKEN>`), base URL prefix (`/blackout-api/v1`), request limits (64 KB JSON), and thread-safe mutation serialization.
- Define standard response envelopes (`ok: true` data envelopes and `ok: false` error envelopes).
- Provide a master dictionary of all error codes (`invalid_request`, `not_found`, `conflict`, `backend_error`, `request_too_large`, `unauthorized`, `method_not_allowed`) and their corresponding HTTP status codes.
- Provide explicit schema tables for all data models: `User`, `ConnectionLink`, `TrafficStats`, and `OnlineUser`.
- Include accurate request/response JSON schemas, URL parameters, header requirements, error cases, and realistic `curl` examples for every endpoint.
- Retain a compact service administration section (systemd commands, token generation, loopback proxying) so developers hosting their own VPS know how to enable and manage the service.

## Non-Goals
- Modifying backend implementation in `api/blackout_api.py` or `lib/api.sh`.
- Altering existing routes, authentication logic, or JSON formats.
- Implementing an interactive OpenAPI/Swagger web UI.

## Anti-Goals
- Omitting error codes, field types, or query parameter constraints.
- Removing service setup and token rotation instructions that self-hosters rely on.

## Constraints
- Must strictly match the behavior and data structures implemented in `api/blackout_api.py`, `lib/api.sh`, and verified in `tests/test_api_http.py`.
- Markdown must render cleanly in standard GitHub Flavored Markdown viewers.

## Approaches Considered
1. **Resource-Grouped Developer Reference (Selected)**: Organizes documentation by domain (Service & Auth -> Conventions & Errors -> Data Models -> User Lifecycle -> Client Provisioning -> Metrics & Observability). Recommended and selected because it directly aligns with how integrating developers build features.
2. **Route-Sequential Reference**: Strictly follows URL path hierarchy. Rejected because it separates related functional domains (e.g. user traffic vs global traffic).
3. **Pure HTTP Contract (Stripping Host/Admin Context)**: Omits systemd and CLI token management. Rejected because developers self-hosting Blackout need operational guidance on enabling the API and retrieving tokens.

## Decisions Made
- **Audience:** External developers integrating applications.
- **Placement:** Overwrite and replace `docs/api.md`.
- **Structure:** Approach 1 (Resource-grouped with retained compact service/auth administration).

## What's Left to the Builder
- Author the complete content of `docs/api.md` detailing all 10 endpoints, full schemas, curl commands, and validation parameters.
