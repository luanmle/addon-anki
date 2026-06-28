# 2026-06-26: Remote Subscriptions Management

## Summary

- What changed: `My Subscriptions` now loads active subscriptions from the platform and shows whether each one is installed locally.
- Why: users can be subscribed to decks on the platform before installing them in Anki, so a local-only list was misleading.

## Scope

- Files/modules touched: `gui/status_dialog.py`, `gui/menu.py`, `sync/engine.py`, `tests/test_sync.py`, `docs/architecture.md`.
- User-visible behavior: remote subscribed decks appear in `My Subscriptions`; decks missing locally expose an `Install` action.
- Internal behavior: `Sync Now` checks active platform subscriptions even when at least one deck is already installed.

## Before

`My Subscriptions` read only local SQLite `remote_decks`, so it showed installed decks only. `Sync Now` installed subscribed decks only when no local decks existed.

## After

`My Subscriptions` calls `GET /subscriptions` through `ApiClient.list_subscriptions()`, then compares each remote subscription with local `remote_decks`. `Sync Now` installs subscribed decks missing from SQLite using `since_release=0`.

## Implementation Notes

- Key decisions: keep `Browse Decks` as catalog; make `My Subscriptions` a remote subscription manager.
- Anki APIs/hooks touched: no new hooks; reused existing `QueryOp` and Qt widgets already used in the add-on.
- Backend API contracts touched: existing `GET /subscriptions` response.
- Storage/config changes: no schema changes.

## Verification

- Automated checks: sync tests cover installing a new subscription while another deck is already installed.
- Manual Anki checks: open `My Subscriptions`, verify subscribed-but-not-installed deck shows `Install`, click `Install`, verify row changes to `Installed`.
- Not run: manual Anki UI check in this environment.

## Risks

- Known risks: `DeckInstaller` still applies note creation on the main-thread success callback, so very large installs can pause Anki during application.
- Rollback notes: restore `StatusDialog` to local-only DB read and remove subscription check from `SyncEngine.sync_all()`.

## Follow-ups

- Move large install application into a collection operation/batched flow.
- Add backend `DELETE /subscriptions/{deck_id}` alias if the desktop add-on later adds unsubscribe from this screen.
