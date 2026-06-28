# Contributing

## Documentation rule

Every behavior change, bug fix, migration, UI change, API contract change, storage change, or release preparation must include documentation in the same change set.

At minimum:

1. Add one entry under `anki_concursos/docs/changes/`.
2. Update the affected long-lived document when behavior or architecture changes:
   - `anki_concursos/docs/architecture.md`
   - `anki_concursos/docs/installation.md`
   - `anki_concursos/config.md`
3. Record verification commands and manual Anki checks that were run or still need to run.

Small mechanical edits may skip a change entry only when they do not change behavior, public contracts, setup, storage, sync, UI, packaging, or tests.

## Change entry naming

Use:

```text
anki_concursos/docs/changes/YYYY-MM-DD-short-slug.md
```

Examples:

```text
anki_concursos/docs/changes/2026-06-26-documentation-process.md
anki_concursos/docs/changes/2026-07-02-sync-timeout-handling.md
```

Start from:

```text
anki_concursos/docs/changes/TEMPLATE.md
```

## Required before completion

- Code or docs changed only where needed.
- Relevant change entry added or explicitly not needed.
- Tests, static checks, or manual Anki checks recorded.
- Any unverified Anki API, hook, storage migration, or backend contract called out.
