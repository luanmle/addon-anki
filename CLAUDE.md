# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
python -m pytest

# Run a single test file
python -m pytest anki_concursos/tests/test_sync.py

# Run a single test by name
python -m pytest anki_concursos/tests/test_sync.py::test_sync_apply_changes

# Build distributable .ankiaddon package
python build_addon.py
```

**Dev installation (symlink to Anki's addons folder):**
```powershell
# Windows (Admin PowerShell)
mklink /D "%APPDATA%\Anki2\addons21\anki_concursos" "C:\path\to\addon-anki\anki_concursos"
```

## Architecture

This is an **Anki add-on** (`anki_concursos/`) that syncs flashcards from the `anki_concursos_docs` backend (FastAPI platform at `../anki_concursos_docs`). Minimum Anki version: `min_point_version = 50` (Anki 25+).

### Initialization Flow

`__init__.py` → `bootstrap.setup()` registers two Anki hooks:
- `profile_did_open` → `hooks/lifecycle.py`: auto-sync if configured
- `main_window_did_init` → `gui/menu.py`: creates the "Anki Concursos" top menu and instantiates `ApiClient` + `DatabaseManager`, storing them on `mw` as `mw.anki_concursos_api` and `mw.anki_concursos_db`

### Sync Flow

There are two distinct sync paths inside `sync/engine.py`:

1. **Bootstrap** (`_bootstrap_subscribed_decks`): triggered when the local DB has no installed decks. Calls `GET /subscriptions`, then for each active subscription installs the full deck snapshot (`since_release=0`).

2. **Incremental** (`sync_all` → `_apply_deck_sync`): for each locally-tracked deck, calls `GET /addon/decks/{id}/sync?since_release={latest_release}` to fetch only changes since the last known release.

The platform has two server-side modes (transparent to addon):
- `since_release=0` → returns **snapshot** of entire deck state, all as action `"added"`
- `since_release=N` → returns **delta** of changes since release N

All network calls happen in a `QueryOp` background thread. All Anki mutations happen in the `on_success` callback (main thread). A backup is created before each incremental apply, and restored on exception.

### `DeckInstaller` (`sync/installer.py`)

Used by the GUI's "Browse Decks" dialog to install a single deck on demand. Mirrors `_install_bootstrap_deck` but is standalone.

### API Layer (`api/`)

- `ApiClient` uses only `urllib.request` (no third-party HTTP libraries). All responses are parsed via `parse_dataclass()`, which strips unknown fields before constructing response dataclasses — this means the addon tolerates extra fields from the platform without crashing.
- The platform companion repo is at `../anki_concursos_docs`. Its schemas are the source of truth for API contracts (`app/schemas/decks.py`, `app/schemas/auth.py`).
- Shared instance lives on `mw.anki_concursos_api`.

### Local Storage (`storage/`)

SQLite at `user_files/anki_concursos.db` (persisted across upgrades). Three tables:
- `remote_decks`: tracks each installed deck with its `latest_release` (used as `since_release` on next sync)
- `remote_cards`: maps `card_id` (platform UUID) ↔ `anki_note_id` (Anki integer)
- `sync_log`: one row per sync operation

### Note Identity and Field Layout

Every managed Anki note has three hidden metadata fields prepended by `NoteTypeManager`:
- `Public ID` — human-readable platform identifier
- `Card ID` — platform UUID (used to find existing notes via `find_note_by_card_id`)
- `Version ID` — platform card version UUID

**Updates never delete and recreate notes** — they call `mw.col.update_note()` on the existing note to preserve Anki scheduling history.

### `use_native_fields` Flag

In `engine.py` and `installer.py`, before creating/updating a note:
```python
use_native_fields = bool(template and change.fields)
```
- `True` when the card was originally uploaded via the addon (has `anki_template` data): `fields` are already Anki field names → pass `field_mapping=None` to `NoteManager`, which sets fields directly.
- `False` for platform-curated cards without upload metadata: uses the manifest's `field_mapping` (`{"Front": "front_text", ...}`) to translate canonical field names.

### Upload Flow (`services/deck_exporter.py`)

`DeckExporter.export_deck()` builds the JSON payload for `POST /addon/decks/upload`. Field mapping is resolved in order: explicit `upload_field_mappings` config → derived from Anki template `{{FieldName}}` references → field order fallback. The `upload_field_mappings` config key (in `config.json`) maps note type names to `{anki_field: canonical_field}` dicts.

### Testing

`conftest.py` mocks `aqt` and `anki` entirely so tests run without Anki installed. `DatabaseManager` is tested against a real temporary SQLite file via the `temp_db` fixture. Sync/installer tests use `MockQueryOp` to run background ops synchronously in-process.

### Environment / Config

`consts.py` defines `API_ENVIRONMENTS` (`local`, `staging`, `production`). Default is `staging`. The active URL is read from `mw.addonManager.getConfig()` at each `ApiClient` instantiation — change `api_environment` or set `api_url` in the add-on config to switch targets.
