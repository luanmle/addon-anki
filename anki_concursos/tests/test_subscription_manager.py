from unittest.mock import MagicMock

from anki_concursos.services.subscription_manager import SubscriptionManager


def test_unsubscribe_and_forget_cancels_remote_then_deletes_local_tracking():
    api = MagicMock()
    db = MagicMock()

    SubscriptionManager(api, db).unsubscribe_and_forget("deck-1")

    api.unsubscribe.assert_called_once_with("deck-1")
    db.delete_deck.assert_called_once_with("deck-1")
