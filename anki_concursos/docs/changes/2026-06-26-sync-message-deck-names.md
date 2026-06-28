# 2026-06-26: Sync Message Deck Names

## Summary

- What changed: Final sync message now names installed and unsubscribed decks.
- Why: Count-only messages hide which deck was actually affected.

## Scope

- Files/modules touched: `anki_concursos/sync/engine.py`, `anki_concursos/tests/test_sync.py`.
- User-visible behavior: Sync toast can say which deck was installed or cleaned up.
- Internal behavior: Message builder now formats deck names from sync payloads.

## Before

Sync toast only said how many decks were installed or cleaned up.

## After

When sync installs a missing subscribed deck, the toast includes the deck name. When sync removes stale local tracking, the toast includes the unsubscribed deck name.

## Verification

- Automated checks: Pending.
- Manual Anki checks: Pending.
- Not run: Real sync toast in Anki after subscription change.

## Risks

- Known risks: Long deck names make toast longer.
- Rollback notes: Revert to count-only message formatting.

## Follow-ups

- N/A
