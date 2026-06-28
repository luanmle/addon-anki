# 2026-06-26: Login Active Email and Logout

## Summary

- What changed: the login/logout dialog now shows the active login email and a `Sair` action when a session exists.
- Why: users need to confirm which account is active and return to the login form after signing out.

## Scope

- Files/modules touched: `api/auth.py`, `api/client.py`, `gui/login_dialog.py`, `tests/test_auth.py`, `tests/test_client.py`, `docs/architecture.md`.
- User-visible behavior: authenticated users see the active email and only the `Sair` action in the login dialog.
- Internal behavior: `user_files/auth.json` now stores the login email with tokens.

## Before

The dialog showed generic logged-in/logged-out status. The token file did not persist the email, so the add-on could not show which account was active without making a network request.

## After

Successful login saves the email from the backend user payload, falling back to the submitted email. Token refresh preserves the stored email. Clicking `Sair` clears the auth file and immediately shows the email and password inputs again.

## Implementation Notes

- Key decisions: use stored email instead of synchronous `/auth/me` in the dialog.
- Anki APIs/hooks touched: no new Anki APIs or hooks.
- Backend API contracts touched: existing `/auth/token` response user email is used when present.
- Storage/config changes: `user_files/auth.json` includes an `email` key.

## Verification

- Automated checks: unit tests added for auth email persistence and client login email storage.
- Manual Anki checks: open `Login / Logout` while logged in, verify email appears, click `Sair`, verify login fields reappear.
- Not run: manual Anki UI check in this environment.

## Risks

- Known risks: existing sessions created before this change have no stored email and will show a fallback message until the user logs in again.
- Rollback notes: remove email persistence and restore generic login dialog state.

## Follow-ups

- N/A
