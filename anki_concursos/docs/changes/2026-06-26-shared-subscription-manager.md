# Shared subscription manager

- What changed: `Browse Decks` and `My Subscriptions` now share the same unsubscribe-and-forget operation.
- Why: Both screens must keep identical semantics when canceling a subscription from the add-on.
- Files/modules touched: `anki_concursos/services/subscription_manager.py`, `anki_concursos/gui/deck_browser.py`, `anki_concursos/gui/status_dialog.py`, `anki_concursos/tests/test_subscription_manager.py`.
- User-visible behavior: No UI change.
- Internal behavior: `SubscriptionManager.unsubscribe_and_forget()` calls the backend unsubscribe endpoint and then removes local sync tracking.
- Backend API contracts touched: Existing `POST /subscriptions/{deck_id}/cancel`.
- Storage/config changes: Existing local deck tracking cleanup.

## Before

Two dialogs duplicated the same unsubscribe logic.

## After

Both dialogs use one shared operation.

## Validation

- Automated checks: subscription manager test, compile checks, full test suite.
- Manual checks: not run in Anki.
