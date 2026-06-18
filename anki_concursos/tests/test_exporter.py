import pytest
from unittest.mock import MagicMock, patch

from anki_concursos.services.deck_exporter import DeckExporter


def _make_mock_note(field_values: dict[str, str], tags: list[str] | None = None) -> MagicMock:
    mock_note = MagicMock()
    mock_note.tags = tags or []
    mock_note.__getitem__.side_effect = lambda key: field_values.get(key)
    return mock_note


@patch("anki_concursos.services.deck_exporter.mw")
def test_export_deck_uses_explicit_basic_mapping(mock_mw):
    exporter = DeckExporter()
    mock_mw.col.decks.get.return_value = {"name": "Direito Constitucional"}
    mock_mw.col.find_notes.return_value = [1001]
    mock_mw.addonManager.getConfig.return_value = {
        "upload_field_mappings": {
            "Anki Concursos Basic": {
                "Front": "front_text",
                "Back": "back_text",
                "Answer": "answer_text",
                "Explanation": "explanation_text",
            }
        }
    }

    mock_note = _make_mock_note(
        {
            "Front": "Questão?",
            "Back": "Resposta.",
            "Answer": "Resposta direta",
            "Explanation": "Comentário.",
        },
        tags=["tag1", "tag2"],
    )
    mock_note.model.return_value = {
        "name": "Anki Concursos Basic",
        "type": 0,
        "flds": [
            {"name": "Front"},
            {"name": "Back"},
            {"name": "Answer"},
            {"name": "Explanation"},
        ],
        "tmpls": [{"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{Back}}"}],
        "css": ".card { color: red; }",
    }
    mock_mw.col.get_note.return_value = mock_note

    payload = exporter.export_deck(1)

    assert payload["deck_name"] == "Direito Constitucional"
    assert len(payload["templates"]) == 1
    assert payload["templates"][0]["field_mapping"] == {
        "Front": "front_text",
        "Back": "back_text",
        "Answer": "answer_text",
        "Explanation": "explanation_text",
    }
    assert payload["notes"][0]["fields"]["Front"] == "Questão?"
    assert payload["notes"][0]["fields"]["Back"] == "Resposta."
    assert payload["notes"][0]["fields"]["Answer"] == "Resposta direta"
    assert payload["notes"][0]["fields"]["Explanation"] == "Comentário."


@patch("anki_concursos.services.deck_exporter.mw")
def test_export_deck_uses_explicit_cloze_mapping(mock_mw):
    exporter = DeckExporter()
    mock_mw.col.decks.get.return_value = {"name": "Getting Started"}
    mock_mw.col.find_notes.return_value = [1002]
    mock_mw.addonManager.getConfig.return_value = {
        "upload_field_mappings": {
            "Getting Started Cloze": {
                "Cloze": "front_text",
                "Extra": "back_text",
                "Deep Dive": "explanation_text",
            }
        }
    }

    mock_note = _make_mock_note(
        {
            "Lesson": "Introdução ao conteúdo",
            "Cloze": "Anki will create {{c1::two::#}} cards from this note.",
            "Extra": "Informação extra",
            "Deep Dive": "Link aprofundado",
        },
        tags=["getting_started"],
    )
    mock_note.model.return_value = {
        "name": "Getting Started Cloze",
        "type": 1,
        "flds": [
            {"name": "Lesson"},
            {"name": "Cloze"},
            {"name": "Extra"},
            {"name": "Deep Dive"},
        ],
        "tmpls": [{"name": "Cloze", "qfmt": "{{cloze:Cloze}}", "afmt": "{{cloze:Cloze}}"}],
        "css": "",
    }
    mock_mw.col.get_note.return_value = mock_note

    payload = exporter.export_deck(1)

    assert payload["templates"][0]["field_mapping"] == {
        "Cloze": "front_text",
        "Extra": "back_text",
        "Deep Dive": "explanation_text",
    }
    assert payload["notes"][0]["fields"]["Lesson"] == "Introdução ao conteúdo"
    assert payload["notes"][0]["fields"]["Cloze"] == "Anki will create {{c1::two::#}} cards from this note."


@patch("anki_concursos.services.deck_exporter.mw")
def test_export_deck_missing_mapping_fails(mock_mw):
    exporter = DeckExporter()
    mock_mw.col.decks.get.return_value = {"name": "Direito Constitucional"}
    mock_mw.col.find_notes.return_value = [1003]
    mock_mw.addonManager.getConfig.return_value = {"upload_field_mappings": {}}

    mock_note = _make_mock_note({"Front": "Questão?", "Back": "Resposta."})
    mock_note.model.return_value = {
        "name": "Anki Concursos Basic",
        "type": 0,
        "flds": [{"name": "Front"}, {"name": "Back"}],
        "tmpls": [{"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{Back}}"}],
        "css": "",
    }
    mock_mw.col.get_note.return_value = mock_note

    with pytest.raises(ValueError) as exc_info:
        exporter.export_deck(1)

    assert "Não há mapeamento explícito" in str(exc_info.value)


@patch("anki_concursos.services.deck_exporter.mw")
def test_export_deck_requires_front_text_mapping(mock_mw):
    exporter = DeckExporter()
    mock_mw.col.decks.get.return_value = {"name": "Direito Constitucional"}
    mock_mw.col.find_notes.return_value = [1004]
    mock_mw.addonManager.getConfig.return_value = {
        "upload_field_mappings": {
            "Anki Concursos Basic": {
                "Back": "back_text",
            }
        }
    }

    mock_note = _make_mock_note({"Front": "Questão?", "Back": "Resposta."})
    mock_note.model.return_value = {
        "name": "Anki Concursos Basic",
        "type": 0,
        "flds": [{"name": "Front"}, {"name": "Back"}],
        "tmpls": [{"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{Back}}"}],
        "css": "",
    }
    mock_mw.col.get_note.return_value = mock_note

    with pytest.raises(ValueError) as exc_info:
        exporter.export_deck(1)

    assert "precisa mapear explicitamente um campo para 'front_text'" in str(exc_info.value)
