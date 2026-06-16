from dataclasses import dataclass
from typing import Optional

@dataclass
class RemoteDeck:
    deck_id: str
    deck_name: str
    anki_deck_id: Optional[int]
    note_type_name: Optional[str]
    latest_release: int
    last_sync: Optional[str]
    created_at: str
    updated_at: str

@dataclass
class RemoteCard:
    card_id: str
    public_id: str
    card_version_id: Optional[str]
    deck_id: str
    anki_note_id: Optional[int]
    card_kind: str
    content_hash: Optional[str]
    status: str
    created_at: str
    updated_at: str

@dataclass
class SyncLogEntry:
    deck_id: str
    from_release: int
    to_release: int
    cards_added: int
    cards_updated: int
    cards_removed: int
    cards_deprecated: int
    synced_at: str
    duration_ms: Optional[int]
    success: bool
    error_message: Optional[str]
    id: Optional[int] = None
