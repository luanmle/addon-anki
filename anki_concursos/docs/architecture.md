# Anki Concursos Add-on Architecture

## Core Principles

1. **Offline-first Synchronization**:
   - The add-on maintains a local SQLite database (`user_files/anki_concursos.db`) tracking remote card identities and versions.
   - Synchronization is purely incremental, based on sequential releases (`since_release`).

2. **Immutable Identities**:
   - The remote backend issues permanent `card_id` and immutable `card_version_id`.
   - The add-on stores these in custom metadata fields (`Card ID`, `Version ID`) on the Anki notes.

3. **Progress Preservation**:
   - Updates never delete and recreate notes. They modify the content fields (`Front`, `Back`, etc.) of existing notes via `mw.col.update_note()`, ensuring that Anki's scheduling history and user progress remain intact.

4. **Background Execution**:
   - Network requests and large batch operations run in background threads using Anki 25+'s `QueryOp` to prevent UI freezing.

## Components

- **API Layer (`api/`)**: Centralized HTTP client using `urllib.request`. Defines strongly-typed Pydantic-like dataclasses for all endpoint responses.
- **Storage Layer (`storage/`)**: Local SQLite wrapper storing `remote_decks`, `remote_cards`, and `sync_log`.
- **Services Layer (`services/`)**: Anki wrappers for Note Type, Deck, and Note manipulations.
- **Sync Engine (`sync/`)**: Orchestrates the incremental sync flow: Fetch -> Backup -> Apply -> Log.
- **GUI (`gui/`)**: PyQt-based dialogs integrated into Anki's top menu.
