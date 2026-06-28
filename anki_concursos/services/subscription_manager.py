from ..api.client import ApiClient
from ..storage.database import DatabaseManager


class SubscriptionManager:
    def __init__(self, api: ApiClient, db: DatabaseManager):
        self.api = api
        self.db = db

    def unsubscribe_and_forget(self, deck_id: str) -> None:
        self.api.unsubscribe(deck_id)
        self.db.delete_deck(deck_id)
