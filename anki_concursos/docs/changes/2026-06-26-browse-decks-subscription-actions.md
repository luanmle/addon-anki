# Browse Decks subscription actions

- What changed: `Browse Decks` now separates local install status from subscription actions.
- Why: `Browse Decks` and `My Subscriptions` should expose the same subscription/install semantics.
- Files/modules touched: `anki_concursos/gui/deck_browser.py`.
- User-visible behavior: The deck catalog now shows `Local Status`, `Install`, and `Subscription` columns. Subscribed decks can be unsubscribed directly from Browse Decks.
- Internal behavior: Unsubscribe calls `ApiClient.unsubscribe()` and removes local sync tracking via `DatabaseManager.delete_deck()`, matching `My Subscriptions`.
- Backend API contracts touched: Existing `POST /subscriptions/{deck_id}/cancel`.
- Storage/config changes: Existing local sync metadata for the deck is removed after successful unsubscribe.

## Before

`Browse Decks` used one action column: `Subscribe`, `Install`, or `Installed`. A subscribed deck could not be unsubscribed from that screen.

## After

`Browse Decks` shows local status independently and exposes install/unsubscribe actions where applicable.

## Validation

- Automated checks: compile and full test suite.
- Manual checks: not run in Anki.
