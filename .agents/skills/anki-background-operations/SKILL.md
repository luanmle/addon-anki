---
name: anki-background-operations
description: Use this skill for network requests, remote synchronization, imports, exports, large searches, bulk card changes, media processing, or any operation that may block Anki's interface; it selects verified QueryOp or CollectionOp patterns and enforces main-thread-only Qt access.
---

# Anki Background Operations

## Goal

Keep Anki responsive and prevent crashes by separating UI work, collection work, and long-running work correctly.

## Workflow

1. Classify the task:
   - read-only or non-undoable work: consider verified `QueryOp`;
   - collection mutation: use an existing or custom verified `CollectionOp`;
   - network-only work: run without collection serialization when supported and verified;
   - trivial UI-only work: stay on the main thread.
2. Collect widget values before launching background work.
3. Pass immutable/plain input to the worker.
4. Never call Qt methods from the worker.
5. Return a small result object from the worker.
6. Update UI in success/failure callbacks on the main thread.
7. Add timeouts, cancellation checks, bounded retries, and progress for operations that can take noticeable time.
8. Ensure errors are converted into actionable user messages and diagnostic logs.
9. Verify operation helper APIs for the target version.

## Thread boundary pattern

```text
UI callback (main thread)
  -> validate and snapshot input
  -> launch QueryOp/CollectionOp
      -> worker performs collection/network/domain work
      -> returns plain result
  -> success/failure callback updates UI
```

## Serialization rules

- Keep collection operations serialized unless the verified API explicitly allows otherwise.
- Network-only operations should not unnecessarily lock the collection.
- Do not run multiple concurrent sync jobs for the same account/deck; use a guard or job coordinator.

## Constraints

- Do not use raw threads when Anki operation helpers cover the use case.
- Do not update a widget, show a dialog, or access webview methods from a background worker.
- Do not perform HTTP calls without explicit connect/read timeouts.
- Do not swallow exceptions in background callbacks.
