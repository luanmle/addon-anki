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
def test_export_deck_matches_note_type_base_name_with_suffix(mock_mw):
    exporter = DeckExporter()
    mock_mw.col.decks.get.return_value = {"name": "Getting Started"}
    mock_mw.col.find_notes.return_value = [1006]
    mock_mw.addonManager.getConfig.return_value = {
        "upload_field_mappings": {
            "Getting Started Basic": {
                "Lesson": "front_text",
                "Extra": "back_text",
            }
        }
    }

    mock_note = _make_mock_note(
        {
            "Lesson": "In Anki, we add and edit notes rather than cards...",
            "Extra": "Extra info",
        }
    )
    mock_note.model.return_value = {
        "name": "Getting Started Basic (Getting Started with Anki / andrew)",
        "type": 0,
        "flds": [{"name": "Lesson"}, {"name": "Extra"}],
        "tmpls": [{"name": "Card 1", "qfmt": "{{Lesson}}", "afmt": "{{Extra}}"}],
        "css": "",
    }
    mock_mw.col.get_note.return_value = mock_note

    payload = exporter.export_deck(1)

    assert payload["templates"][0]["note_type"] == "Getting Started Basic (Getting Started with Anki / andrew)"
    assert payload["templates"][0]["field_mapping"] == {
        "Lesson": "front_text",
        "Extra": "back_text",
    }
    assert payload["notes"][0]["fields"]["Lesson"] == "In Anki, we add and edit notes rather than cards..."


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
def test_export_deck_derives_mapping_from_templates_without_config(mock_mw):
    exporter = DeckExporter()
    mock_mw.col.decks.get.return_value = {"name": "Direito Constitucional"}
    mock_mw.col.find_notes.return_value = [1003]
    mock_mw.addonManager.getConfig.return_value = {}

    mock_note = _make_mock_note(
        {
            "Front": "Questão?",
            "Back": "Resposta.",
        }
    )
    mock_note.model.return_value = {
        "name": "Anki Concursos Basic",
        "type": 0,
        "flds": [{"name": "Front"}, {"name": "Back"}],
        "tmpls": [{"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{Back}}"}],
        "css": "",
    }
    mock_mw.col.get_note.return_value = mock_note

    payload = exporter.export_deck(1)

    assert payload["templates"][0]["field_mapping"] == {
        "Front": "front_text",
        "Back": "back_text",
    }
    assert payload["notes"][0]["fields"]["Front"] == "Questão?"


@patch("anki_concursos.services.deck_exporter.mw")
def test_export_deck_cloze_model_without_markup_exports_as_basic(mock_mw):
    """Cloze note type whose notes ALL lack {{c1::}} markup must export as basic."""
    exporter = DeckExporter()
    mock_mw.col.decks.get.return_value = {"name": "Certo Errado"}
    mock_mw.col.find_notes.return_value = [2001]
    mock_mw.addonManager.getConfig.return_value = {}

    mock_note = _make_mock_note(
        {
            "Afirmação": "A Terra é redonda.",
            "Certo - Errado": "Certo",
        }
    )
    notetype = {
        "name": "Certo Errado",
        "type": 1,
        "flds": [{"name": "Afirmação"}, {"name": "Certo - Errado"}],
        "tmpls": [{"name": "Card 1", "qfmt": "{{Afirmação}}", "afmt": "{{Certo - Errado}}"}],
        "css": "",
    }
    mock_note.model.return_value = notetype
    mock_mw.col.get_note.return_value = mock_note

    payload = exporter.export_deck(1)

    assert payload["notes"][0]["card_kind"] == "basic"
    assert payload["templates"][0]["card_kind"] == "basic"
    assert payload["notes"][0]["fields"]["Afirmação"] == "A Terra é redonda."


@patch("anki_concursos.services.deck_exporter.mw")
def test_export_deck_mixed_cloze_model_all_exported_as_cloze(mock_mw):
    """Mixed cloze model (some notes with markup, some without) → all exported as cloze.

    The platform requires note.card_kind == template.card_kind. Pre-scan detects
    ANY note with cloze markup → canonical card_kind = 'cloze' for the whole type.
    """
    exporter = DeckExporter()
    mock_mw.col.decks.get.return_value = {"name": "ESQ Cloze"}
    mock_mw.col.find_notes.return_value = [3001, 3002]
    mock_mw.addonManager.getConfig.return_value = {}

    notetype = {
        "name": "3. ESQ-Cloze [v5]+",
        "type": 1,
        "flds": [{"name": "Texto"}, {"name": "Extra"}],
        "tmpls": [{"name": "Cloze", "qfmt": "{{cloze:Texto}}", "afmt": "{{cloze:Texto}}{{Extra}}"}],
        "css": "",
    }
    note_cloze = _make_mock_note({"Texto": "Brasil é uma república {{c1::federativa}}.", "Extra": ""})
    note_cloze.model.return_value = notetype
    note_cloze.tags = []
    note_basic = _make_mock_note({"Texto": "Artigo 5 trata de direitos fundamentais.", "Extra": ""})
    note_basic.model.return_value = notetype
    note_basic.tags = []

    mock_mw.col.get_note.side_effect = [note_cloze, note_basic, note_cloze, note_basic]

    payload = exporter.export_deck(1)

    assert payload["templates"][0]["card_kind"] == "cloze"
    assert all(n["card_kind"] == "cloze" for n in payload["notes"])


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

    assert "Não foi possível determinar um campo para 'front_text'" in str(exc_info.value)
