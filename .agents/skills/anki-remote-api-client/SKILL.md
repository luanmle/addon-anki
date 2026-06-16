---
name: anki-remote-api-client
description: Use this skill when an Anki add-on must call FastAPI, REST, GraphQL, AnkiHub-like services, authentication endpoints, download updates, upload edits, or synchronize remote data; it designs a typed API boundary with timeouts, retries, idempotency, offline behavior, and background execution.
---

# Anki Remote API Client

## Goal

Connect an add-on to a remote service without freezing Anki, leaking credentials, corrupting local data, or coupling UI code to transport details.

## Workflow

1. Read the backend contract first: base URL, endpoints, schemas, pagination, authentication, errors, rate limits, versioning, and idempotency behavior.
2. Never connect the desktop add-on directly to the remote SQL database. Use the service API.
3. Create layers:
   - transport/client;
   - typed request/response models;
   - authentication/session service;
   - sync planner/conflict policy;
   - Anki collection adapter;
   - UI/controller.
4. Run HTTP work through `anki-background-operations`.
5. Configure explicit connect/read timeouts and a descriptive user agent.
6. Retry only transient, idempotent requests with exponential backoff and jitter.
7. Do not retry authentication failures, validation failures, or non-idempotent mutations blindly.
8. Validate all remote payloads before applying them to the collection.
9. Apply collection changes through `anki-collection-data` operations in bounded batches.
10. Persist cursors/checkpoints so interrupted sync can resume safely.
11. Define conflict handling before implementing bidirectional sync.
12. Redact tokens and personal data from logs and error reports.

## Authentication rules

- Prefer short-lived access tokens with a documented refresh flow.
- Keep tokens out of `config.json`, source control, URLs, and logs.
- Use an OS credential store when the project supports it; otherwise document the fallback and its limitations.
- On logout, revoke when supported and remove local credentials/checkpoints tied to the account.

## Sync invariants

- Same remote event applied twice must not duplicate notes/cards.
- Remote identity mapping must be explicit and durable.
- Local user edits must not be overwritten without a declared policy.
- A partial failure must leave enough state to retry or reconcile.
- Network success does not imply collection mutation success; record stages separately.

## Dependency policy

Before adding an HTTP or validation library, verify whether it is already bundled with the target Anki build. If not, vendor or package it according to Anki add-on dependency constraints and license requirements.

## Constraints

- Do not call the API synchronously from a button or hook callback.
- Do not use infinite retries or missing timeouts.
- Do not trust remote HTML, field names, IDs, or enum values without validation.
- Do not store server secrets or database credentials in the add-on.
