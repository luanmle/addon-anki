# Auth-required menu actions

- What changed: Menu actions that require authenticated backend access now check login state first.
- Why: Sync, catalog, subscriptions, and upload all depend on authenticated API calls. Starting them while logged out produced later API errors instead of a clear login flow.
- Files/modules touched: `anki_concursos/gui/menu.py`, `anki_concursos/tests/test_menu.py`.
- User-visible behavior: If the user is logged out and clicks an authenticated action, the login dialog opens first. If login is canceled, the action is skipped with a `Login Required` warning.
- Internal behavior: `menu._ensure_authenticated()` centralizes the token check and login prompt.
- Backend API contracts touched: None.
- Storage/config changes: None.

## Before

Actions such as `Sync Now`, `Browse Decks`, and `My Subscriptions` could start while logged out and fail later with auth errors.

## After

Those actions require a token before continuing.

## Validation

- Automated checks: menu tests, compile checks, full test suite.
- Manual checks: not run in Anki.
