---
name: anki-collection-data
description: Use this skill for reading or changing Anki cards, notes, decks, deck configurations, note types, tags, scheduler data, search results, media, or collection state; it favors public collection methods and undoable operations while preventing unsafe direct SQL and schema changes.
---

# Anki Collection and Data

## Goal

Manipulate collection data in a sync-aware, undo-aware, thread-correct way without corrupting Anki's database.

## Workflow

1. Confirm a collection is loaded before using `mw.col`.
2. Identify whether the operation is:
   - read-only;
   - mutating and undoable;
   - mutating but intentionally non-undoable;
   - media-related;
   - scheduler-related.
3. Verify the public `Collection`, card, note, deck, model, media, or operation API.
4. Prefer public methods such as get/update/find/save operations over direct SQL writes.
5. For user-triggered mutations, prefer existing `CollectionOp` helpers when available.
6. For custom mutations, group changes into a coherent undo entry according to verified Anki APIs.
7. For batches, pass IDs/plain values into the operation and reacquire objects in the operation context.
8. Refresh affected UI through operation helpers or verified hooks, not arbitrary widget poking.
9. Add tests for pure transformations and a manual collection backup test for risky migrations.

## Direct database policy

- Read-only SQL may be acceptable for carefully measured queries when no public method exists.
- Direct writes bypass important sync/change tracking and are forbidden by default.
- Never modify the schema of Anki's built-in tables.
- Add-on-specific larger data belongs outside built-in tables, with a documented persistence strategy.

## Sync and identity rules

- Treat note/card/deck IDs as persistent identifiers, not list positions.
- Make repeated remote updates idempotent.
- Do not assume rendered HTML equals stored field text.
- Do not store large blobs in `mw.col.conf`; it is intended for small synced options.

## Constraints

- Do not access `mw.col` at import time.
- Do not retain mutable Anki objects across background/main-thread boundaries.
- Do not call scheduler internals based on outdated examples without source verification.
- Do not bypass undo/sync semantics for convenience.
