import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Optional, Tuple
from datetime import datetime, timezone

from aqt import mw

from .models import RemoteDeck, RemoteCard, SyncLogEntry

class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            if mw and mw.addonManager:
                # Find the actual add-on directory path to put the user_files folder
                addon_dir = Path(__file__).parent.parent
                self.db_path = addon_dir / "user_files" / "anki_concursos.db"
            else:
                self.db_path = Path("anki_concursos.db")
        else:
            self.db_path = db_path
            
        # Ensure parent directory exists
        self.db_path.parent.mkdir(exist_ok=True, parents=True)
            
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._local.conn.execute("PRAGMA foreign_keys = ON;")
        return self._local.conn

    def close(self) -> None:
        if hasattr(self._local, "conn"):
            try:
                self._local.conn.close()
            except Exception:
                pass
            delattr(self._local, "conn")


    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_db(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS remote_decks (
            deck_id          TEXT PRIMARY KEY,
            deck_name        TEXT NOT NULL,
            anki_deck_id     INTEGER,
            note_type_name   TEXT,
            latest_release   INTEGER NOT NULL DEFAULT 0,
            last_sync        TEXT,
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS remote_cards (
            card_id            TEXT PRIMARY KEY,
            public_id          TEXT NOT NULL,
            card_version_id    TEXT,
            deck_id            TEXT NOT NULL REFERENCES remote_decks(deck_id),
            anki_note_id       INTEGER,
            card_kind          TEXT NOT NULL DEFAULT 'basic',
            content_hash       TEXT,
            remote_fields      TEXT,
            status             TEXT NOT NULL DEFAULT 'active',
            created_at         TEXT NOT NULL,
            updated_at         TEXT NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS sync_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id      TEXT NOT NULL REFERENCES remote_decks(deck_id),
            from_release INTEGER NOT NULL,
            to_release   INTEGER NOT NULL,
            cards_added  INTEGER NOT NULL DEFAULT 0,
            cards_updated INTEGER NOT NULL DEFAULT 0,
            cards_removed INTEGER NOT NULL DEFAULT 0,
            cards_deprecated INTEGER NOT NULL DEFAULT 0,
            synced_at    TEXT NOT NULL,
            duration_ms  INTEGER,
            success      INTEGER NOT NULL DEFAULT 1,
            error_message TEXT
        );
        """
        with self.transaction() as c:
            c.executescript(schema)
            self._ensure_column(c, "remote_cards", "remote_fields", "TEXT")

    def _ensure_column(self, cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in cursor.fetchall()}
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            
    # --- Deck Methods ---
    
    def get_deck(self, deck_id: str) -> Optional[RemoteDeck]:
        with self.transaction() as c:
            c.execute("SELECT * FROM remote_decks WHERE deck_id = ?", (deck_id,))
            row = c.fetchone()
            if row:
                return RemoteDeck(**dict(row))
        return None
        
    def upsert_deck(self, deck: RemoteDeck) -> None:
        with self.transaction() as c:
            c.execute("""
                INSERT INTO remote_decks 
                (deck_id, deck_name, anki_deck_id, note_type_name, latest_release, last_sync, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(deck_id) DO UPDATE SET
                    deck_name=excluded.deck_name,
                    anki_deck_id=excluded.anki_deck_id,
                    note_type_name=excluded.note_type_name,
                    latest_release=excluded.latest_release,
                    last_sync=excluded.last_sync,
                    updated_at=excluded.updated_at
            """, (deck.deck_id, deck.deck_name, deck.anki_deck_id, deck.note_type_name,
                  deck.latest_release, deck.last_sync, deck.created_at, deck.updated_at))
                  
    def get_all_decks(self) -> List[RemoteDeck]:
        with self.transaction() as c:
            c.execute("SELECT * FROM remote_decks")
            return [RemoteDeck(**dict(row)) for row in c.fetchall()]
            
    def delete_deck(self, deck_id: str) -> None:
        with self.transaction() as c:
            c.execute("DELETE FROM remote_cards WHERE deck_id = ?", (deck_id,))
            c.execute("DELETE FROM sync_log WHERE deck_id = ?", (deck_id,))
            c.execute("DELETE FROM remote_decks WHERE deck_id = ?", (deck_id,))

    def repair_integrity(self) -> int:
        """Repair safe local metadata issues and raise on SQLite corruption.

        Only add-on sync metadata is modified. Existing Anki notes/decks are not
        touched here.
        """
        with self.transaction() as c:
            c.execute("""
                DELETE FROM remote_cards
                WHERE deck_id NOT IN (SELECT deck_id FROM remote_decks)
            """)
            removed_cards = c.rowcount if c.rowcount is not None else 0
            c.execute("""
                DELETE FROM sync_log
                WHERE deck_id NOT IN (SELECT deck_id FROM remote_decks)
            """)
            removed_logs = c.rowcount if c.rowcount is not None else 0

            c.execute("PRAGMA integrity_check")
            integrity_rows = [row[0] for row in c.fetchall()]
            if integrity_rows != ["ok"]:
                raise RuntimeError("Local sync database integrity check failed: " + "; ".join(integrity_rows))

            c.execute("PRAGMA foreign_key_check")
            fk_rows: List[Tuple] = [tuple(row) for row in c.fetchall()]
            if fk_rows:
                raise RuntimeError(f"Local sync database foreign key check failed: {fk_rows}")

            return removed_cards + removed_logs
            
    # --- Card Methods ---
    
    def get_card(self, card_id: str) -> Optional[RemoteCard]:
        with self.transaction() as c:
            c.execute("SELECT * FROM remote_cards WHERE card_id = ?", (card_id,))
            row = c.fetchone()
            if row:
                return self._card_from_row(row)
        return None
        
    def get_card_by_anki_note_id(self, anki_note_id: int) -> Optional[RemoteCard]:
        with self.transaction() as c:
            c.execute("SELECT * FROM remote_cards WHERE anki_note_id = ?", (anki_note_id,))
            row = c.fetchone()
            if row:
                return self._card_from_row(row)
        return None
        
    def get_active_cards_by_deck(self, deck_id: str) -> List[RemoteCard]:
        with self.transaction() as c:
            c.execute(
                "SELECT * FROM remote_cards WHERE deck_id = ? AND status = 'active'",
                (deck_id,),
            )
            return [self._card_from_row(row) for row in c.fetchall()]

    def upsert_card(self, card: RemoteCard) -> None:
        remote_fields = (
            json.dumps(card.remote_fields, ensure_ascii=False)
            if card.remote_fields is not None
            else None
        )
        with self.transaction() as c:
            c.execute("""
                INSERT INTO remote_cards 
                (card_id, public_id, card_version_id, deck_id, anki_note_id, card_kind, content_hash, remote_fields, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    card_version_id=excluded.card_version_id,
                    anki_note_id=excluded.anki_note_id,
                    card_kind=excluded.card_kind,
                    content_hash=excluded.content_hash,
                    remote_fields=excluded.remote_fields,
                    status=excluded.status,
                    updated_at=excluded.updated_at
            """, (card.card_id, card.public_id, card.card_version_id, card.deck_id, 
                  card.anki_note_id, card.card_kind, card.content_hash, remote_fields, card.status, 
                  card.created_at, card.updated_at))

    def _card_from_row(self, row: sqlite3.Row) -> RemoteCard:
        data = dict(row)
        raw_fields = data.get("remote_fields")
        if isinstance(raw_fields, str) and raw_fields:
            try:
                data["remote_fields"] = json.loads(raw_fields)
            except json.JSONDecodeError:
                data["remote_fields"] = None
        else:
            data["remote_fields"] = None
        return RemoteCard(**data)
                  
    def update_card_status(self, card_id: str, status: str, version_id: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as c:
            if version_id:
                c.execute("""
                    UPDATE remote_cards SET status = ?, card_version_id = ?, updated_at = ?
                    WHERE card_id = ?
                """, (status, version_id, now, card_id))
            else:
                c.execute("""
                    UPDATE remote_cards SET status = ?, updated_at = ?
                    WHERE card_id = ?
                """, (status, now, card_id))
                
    def delete_cards_by_deck(self, deck_id: str) -> None:
        with self.transaction() as c:
            c.execute("DELETE FROM remote_cards WHERE deck_id = ?", (deck_id,))

    # --- Sync Log Methods ---
    
    def add_sync_log(self, entry: SyncLogEntry) -> None:
        with self.transaction() as c:
            c.execute("""
                INSERT INTO sync_log 
                (deck_id, from_release, to_release, cards_added, cards_updated, 
                 cards_removed, cards_deprecated, synced_at, duration_ms, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (entry.deck_id, entry.from_release, entry.to_release, entry.cards_added,
                  entry.cards_updated, entry.cards_removed, entry.cards_deprecated, 
                  entry.synced_at, entry.duration_ms, 1 if entry.success else 0, entry.error_message))

    def get_sync_logs(self, deck_id: str, limit: int = 10) -> List[SyncLogEntry]:
        with self.transaction() as c:
            c.execute("""
                SELECT * FROM sync_log
                WHERE deck_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (deck_id, limit))
            rows = []
            for row in c.fetchall():
                data = dict(row)
                data["success"] = bool(data["success"])
                rows.append(SyncLogEntry(**data))
            return rows
