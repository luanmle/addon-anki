# Dynamic login menu label

- What changed: The menu login action now reflects the current auth state.
- Why: `Login / Logout` was ambiguous after login; users could not see active session from the menu.
- Files/modules touched: `anki_concursos/gui/menu.py`, `anki_concursos/tests/test_menu.py`.
- User-visible behavior: Logged-out users see `Login`. Logged-in users see `Logged in: <email>` when an email is stored, otherwise `Logged in`.
- Internal behavior: `refresh_menu_state()` updates the action when the menu opens and after login dialog closes.
- Backend API contracts touched: None.
- Storage/config changes: None.

## Before

The menu always showed `Login / Logout`.

## After

The menu label updates from local auth state.

## Validation

- Automated checks: menu tests, compile checks, full test suite.
- Manual checks: not run in Anki.
