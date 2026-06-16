---
name: anki-config-storage
description: Use this skill for Anki add-on settings, config.json, config.md, custom preferences dialogs, user_files, caches, local mappings, synchronized small options, credentials, or migrations of persisted add-on data; it chooses storage based on lifecycle, sensitivity, size, and sync requirements.
---

# Anki Configuration and Storage

## Goal

Persist settings and add-on data without losing user files during upgrades, exposing secrets, or abusing Anki's collection database.

## Workflow

1. Classify each value by:
   - default vs user-specific;
   - secret vs non-secret;
   - small vs large;
   - synchronized vs local-only;
   - disposable cache vs authoritative data.
2. Use `config.json` for shipped default key/value settings and `config.md` for user documentation.
3. Read/write configuration through the verified add-on manager API.
4. Keep custom files under `user_files/` so upgrades preserve them.
5. Use `mw.col.conf` only for small settings that truly need collection sync.
6. Use an explicit local store for mappings/checkpoints too large or structured for simple config.
7. Version every non-trivial stored schema and write forward migrations.
8. Use atomic writes for local files: write temporary file, flush, then replace.
9. Validate and merge configuration with defaults; handle missing and unknown keys deliberately.
10. Redact secrets from diagnostics and exports.

## Storage decision table

| Need | Preferred location |
|---|---|
| Shipped simple defaults | `config.json` |
| Human-readable config help | `config.md` |
| User-edited files preserved on upgrade | `user_files/` |
| Small options synced with collection | verified collection config mechanism |
| Disposable HTTP/media cache | local cache under `user_files/` with cleanup |
| Access/refresh token | OS credential store when available; documented secure fallback |

## Migration rules

- Include `schema_version` for structured data.
- Back up before destructive migration.
- Make migrations idempotent.
- Never downgrade silently when a newer schema is detected.

## Constraints

- Do not depend on modifications inside installed source files; upgrades replace them.
- Do not use config for large datasets.
- Do not hardcode credentials or commit real config values.
- Do not claim `user_files` is synchronized by Anki unless separately implemented and verified.
