---
name: anki-testing-quality-gate
description: Use this skill before declaring any Anki add-on feature, refactor, bug fix, migration, or release complete; it runs deterministic static checks, typing and unit tests, audits common Anki hazards, and produces a manual test matrix for behaviors that require a real Anki profile.
---

# Anki Testing and Quality Gate

## Goal

Replace confidence-by-inspection with repeatable evidence and clearly separate automated verification from manual Anki integration testing.

## Workflow

1. Run the bundled audit:

```bash
python scripts/validate_addon.py <addon-package-or-project-root>
```

2. Compile Python modules.
3. Run the repository formatter/linter without changing configured policy.
4. Run mypy or the project's type checker with Anki/aqt stubs matching the target version.
5. Run unit tests for pure logic, API schema validation, mapping, conflict resolution, and migrations.
6. Mock at the Anki adapter boundary, not deep inside domain logic.
7. Inspect the diff for:
   - invented or private APIs;
   - direct PyQt imports;
   - legacy hooks;
   - collection access at import time;
   - direct SQL writes/schema changes;
   - synchronous network calls in UI callbacks;
   - unbounded retries and missing timeouts;
   - unredacted secrets;
   - broad exception swallowing.
8. Build a manual matrix for real Anki behavior.
9. Record exact commands and results.

## Manual integration matrix

At minimum, test applicable cases:

- clean profile and existing profile;
- profile open/close/switch;
- add-on enabled/disabled/reloaded;
- target reviewer/editor/browser lifecycle;
- repeated action invocation;
- network online, timeout, offline, invalid auth, partial response;
- collection mutation followed by undo, sync, restart, and re-open;
- night mode and supported operating systems;
- oldest and newest supported Anki versions.

## Failure policy

- A failed automated check blocks completion unless the failure is pre-existing and documented with evidence.
- A skipped real-Anki test must be reported as not tested, never as passed.
- Warnings from the bundled audit require review; they are not automatically defects.

## Constraints

- Do not claim end-to-end success without running Anki when the feature depends on Anki UI/lifecycle.
- Do not disable typing or tests to make the gate pass.
- Do not mock away the behavior under test.
- Do not hide failing checks in summarized output.
