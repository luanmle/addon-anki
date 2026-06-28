# 2026-06-26: Sync Message Summary

## Summary

- What changed: Final sync message now includes counts for installed subscribed decks and removed local tracking for unsubscribed decks.
- Why: User needs see which extra actions sync applied, not only card delta count.

## Scope

- Files/modules touched: `anki_concursos/sync/engine.py`, `anki_concursos/tests/test_sync.py`.
- User-visible behavior: Sync toast reports cleanup/install actions when they happen.
- Internal behavior: Message builder keeps card sync result intact and appends extra action summary.

## Before

Final sync message only reflected card delta or a generic up-to-date state.

## After

When sync also installs missing subscribed decks or removes local tracking for unsubscribed decks, the final message includes those counts.

## Verification

- Automated checks: Pending.
- Manual Anki checks: Pending.
- Not run: Real sync run in Anki after platform subscription changes.

## Risks

- Known risks: Message is longer, but only when extra actions happen.
- Rollback notes: Restore old message builder if wording is too noisy.

## Follow-ups

- N/A
