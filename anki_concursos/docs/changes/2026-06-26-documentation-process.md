# 2026-06-26: Documentation Process

## Summary

- What changed: added a required documentation process for implementation changes.
- Why: keep add-on behavior, verification, and manual Anki test notes traceable across future work.

## Scope

- Files/modules touched: documentation only.
- User-visible behavior: none.
- Internal behavior: future changes should include a dated entry under `anki_concursos/docs/changes/`.

## Before

The repository had architecture and installation notes, but no standard place to record implementation changes, verification results, risks, or manual Anki checks.

## After

The repository has:

- a root `CONTRIBUTING.md` documentation rule;
- a docs index at `anki_concursos/docs/README.md`;
- a change log process at `anki_concursos/docs/changes/README.md`;
- a reusable template at `anki_concursos/docs/changes/TEMPLATE.md`.

## Implementation Notes

- Key decisions: use one dated Markdown file per meaningful change.
- Anki APIs/hooks touched: N/A.
- Backend API contracts touched: N/A.
- Storage/config changes: N/A.

## Verification

- Automated checks: N/A, documentation-only change.
- Manual Anki checks: N/A, no runtime behavior changed.
- Not run: `python -m pytest`, because no code changed.

## Risks

- Known risks: process depends on contributors following the rule; no automated enforcement added.
- Rollback notes: remove the documentation files and README link if the process is replaced.

## Follow-ups

- Consider adding a CI/docs check that requires a `docs/changes/` entry for code changes.
