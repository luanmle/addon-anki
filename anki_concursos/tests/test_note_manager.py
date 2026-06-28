from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from anki_concursos.services.note_manager import NoteManager


def test_note_exists_detects_existing_note():
    with patch("anki_concursos.services.note_manager.mw") as mock_mw:
        mock_mw.col.get_note.return_value = MagicMock()

        assert NoteManager().note_exists(123) is True


def test_note_exists_returns_false_when_get_note_fails():
    with patch("anki_concursos.services.note_manager.mw") as mock_mw:
        mock_mw.col.get_note.side_effect = Exception("missing")

        assert NoteManager().note_exists(123) is False


def test_note_modified_after_detects_local_edit_after_sync_timestamp():
    note = MagicMock()
    note.mod = int(datetime(2026, 6, 26, 11, 0, tzinfo=timezone.utc).timestamp())

    with patch("anki_concursos.services.note_manager.mw") as mock_mw:
        mock_mw.col.get_note.return_value = note

        assert NoteManager().note_modified_after(
            123,
            "2026-06-26T10:00:00+00:00",
        ) is True


def test_note_modified_after_ignores_note_saved_before_sync_timestamp():
    note = MagicMock()
    note.mod = int(datetime(2026, 6, 26, 9, 0, tzinfo=timezone.utc).timestamp())

    with patch("anki_concursos.services.note_manager.mw") as mock_mw:
        mock_mw.col.get_note.return_value = note

        assert NoteManager().note_modified_after(
            123,
            "2026-06-26T10:00:00+00:00",
        ) is False


def _fake_note(fields):
    note = MagicMock()
    note.keys.return_value = list(fields.keys())
    note.__getitem__.side_effect = lambda k: fields[k]
    return note


def test_note_differs_from_true_when_field_changed():
    note = _fake_note({"Front": "edited", "Back": "A"})
    with patch("anki_concursos.services.note_manager.mw") as mock_mw:
        mock_mw.col.get_note.return_value = note
        assert NoteManager().note_differs_from(
            1, {"Front": "Q", "Back": "A"}
        ) is True


def test_note_differs_from_false_when_content_matches_baseline():
    note = _fake_note({"Front": "Q", "Back": "A"})
    with patch("anki_concursos.services.note_manager.mw") as mock_mw:
        mock_mw.col.get_note.return_value = note
        assert NoteManager().note_differs_from(
            1, {"Front": "Q", "Back": "A"}
        ) is False


def test_note_differs_from_ignores_protected_fields():
    note = _fake_note({"Front": "Q", "Personal": "minha nota"})
    with patch("anki_concursos.services.note_manager.mw") as mock_mw:
        mock_mw.col.get_note.return_value = note
        # Personal differs from baseline but is protected → not a difference
        assert NoteManager().note_differs_from(
            1, {"Front": "Q", "Personal": "remoto"}, ignore={"Personal"}
        ) is False


def test_note_differs_from_true_without_baseline():
    with patch("anki_concursos.services.note_manager.mw") as mock_mw:
        mock_mw.col.get_note.return_value = _fake_note({"Front": "Q"})
        assert NoteManager().note_differs_from(1, None) is True


def test_note_modified_after_returns_true_on_exception():
    """C2: error during comparison must not silently allow overwriting a local edit."""
    with patch("anki_concursos.services.note_manager.mw") as mock_mw:
        mock_mw.col.get_note.side_effect = RuntimeError("collection locked")
        assert NoteManager().note_modified_after(123, "2026-06-26T10:00:00+00:00") is True
