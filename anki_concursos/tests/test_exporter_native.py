import pytest
from unittest.mock import MagicMock, patch

from anki_concursos.services.deck_exporter import DeckExporter


def _make_mock_note(field_values: dict[str, str], tags: list[str] | None = None) -> MagicMock:
    mock_note = MagicMock()
    mock_note.tags = tags or []
    mock_note.__getitem__.side_effect = lambda key: field_values.get(key)
    return mock_note


@patch("anki_concursos.services.deck_exporter.mw")
def test_export_deck_emits_one_upload_note_per_template(mock_mw):
    exporter = DeckExporter()
    mock_mw.col.decks.get.return_value = {"name": "Vocabulario"}
    mock_mw.col.find_notes.return_value = [1007]
    mock_mw.addonManager.getConfig.return_value = {}

    mock_note = _make_mock_note(
        {
            "Termo": "Mandado de seguranca",
            "Definicao": "Remedio constitucional",
        }
    )
    mock_note.id = 1007
    mock_note.guid = "guid-1007"
    mock_note.model.return_value = {
        "name": "Vocabulario",
        "type": 0,
        "flds": [{"name": "Termo"}, {"name": "Definicao"}],
        "tmpls": [
            {"name": "Forward", "qfmt": "{{Termo}}", "afmt": "{{Definicao}}"},
            {"name": "Reverse", "qfmt": "{{Definicao}}", "afmt": "{{Termo}}"},
        ],
        "css": "",
    }
    mock_mw.col.get_note.return_value = mock_note

    payload = exporter.export_deck(1)

    assert len(payload["templates"]) == 2
    assert [note["template_name"] for note in payload["notes"]] == [
        "Forward",
        "Reverse",
    ]
    assert all(note["source_note_id"] == "1007" for note in payload["notes"])
    assert all(note["source_note_guid"] == "guid-1007" for note in payload["notes"])
    assert all(note["source_deck_path"] == "Vocabulario" for note in payload["notes"])
