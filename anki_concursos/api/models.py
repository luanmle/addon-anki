from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class UserResponse:
    user_id: str
    email: str
    display_name: str
    role: str

@dataclass
class TokenResponse:
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse
    refresh_token: Optional[str] = None


@dataclass
class SubscribableDeckResponse:
    deck_id: str
    name: str
    description: Optional[str]
    latest_release: int
    subscribed: bool
    active_card_count: int

@dataclass
class SubscribableDeckListResponse:
    items: List[SubscribableDeckResponse]
    page: int
    page_size: int
    total: int
    pages: int

@dataclass
class DeckSubscriptionResponse:
    subscription_id: str
    deck_id: str
    deck_name: str
    latest_release: int
    active_card_count: int
    subscribed_at: str
    unsubscribed_at: Optional[str] = None

@dataclass
class DeckSubscriptionListResponse:
    items: List[DeckSubscriptionResponse]
    total: int

@dataclass
class AnkiDeckManifestResponse:
    deck_id: str
    name: str
    description: Optional[str]
    latest_release: int
    note_type: str
    fields: List[str]
    field_mapping: Dict[str, str]
    supported_note_types: Dict[str, Any]
    tags: List[str] = field(default_factory=list)
    templates: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class AnkiSyncChangeResponse:
    release_id: str
    release_number: int
    published_at: str
    action: str
    card_id: str
    public_id: str
    old_card_version_id: Optional[str]
    new_card_version_id: Optional[str]
    card_kind: Optional[str] = None
    note_type: Optional[str] = None
    template_name: Optional[str] = None
    fields: Optional[Dict[str, str]] = None
    template: Optional[Dict[str, Any]] = None
    source_note_id: Optional[str] = None
    source_note_guid: Optional[str] = None
    source_deck_path: Optional[str] = None
    tags: List[str] = field(default_factory=list)

@dataclass
class AnkiDeckSyncResponse:
    deck_id: str
    from_release: int
    to_release: int
    has_changes: bool
    changes: List[AnkiSyncChangeResponse]
    page: Optional[int] = None
    pages: Optional[int] = None
    total_changes: Optional[int] = None

@dataclass
class AnkiDeckTemplateResponse:
    template_name: str
    note_type: str
    card_kind: str
    fields: List[str]
    field_mapping: Dict[str, str]
    front_html: str
    back_html: str
    styling_css: str = ""

