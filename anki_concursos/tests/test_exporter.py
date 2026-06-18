import pytest
from unittest.mock import MagicMock, patch
from anki_concursos.services.deck_exporter import DeckExporter

def test_resolve_field_mapping():
    exporter = DeckExporter()
    
    # Cloze resolving
    cloze_mapping = exporter._resolve_field_mapping(["Text", "Extra"], "cloze")
    assert cloze_mapping["Text"] == "front_text"
    assert cloze_mapping["Extra"] == "back_text"
    
    # Basic resolving with Portuguese field names
    basic_mapping = exporter._resolve_field_mapping(["Pergunta", "Verso", "Gabarito", "Comentario"], "basic")
    assert basic_mapping["Pergunta"] == "front_text"
    assert basic_mapping["Verso"] == "back_text"
    assert basic_mapping["Gabarito"] == "answer_text"
    assert basic_mapping["Comentario"] == "explanation_text"
    
    # Fallback positioning
    fallback_mapping = exporter._resolve_field_mapping(["CustomField1", "CustomField2"], "basic")
    assert fallback_mapping["CustomField1"] == "front_text"
    assert fallback_mapping["CustomField2"] == "back_text"

@patch("anki_concursos.services.deck_exporter.mw")
def test_export_deck_basic_success(mock_mw):
    exporter = DeckExporter()
    
    # Mock deck dict
    mock_mw.col.decks.get.return_value = {"name": "Direito Constitucional"}
    
    # Mock find_notes returning note IDs
    mock_mw.col.find_notes.return_value = [1001]
    
    # Mock note object
    mock_note = MagicMock()
    mock_note.tags = ["tag1", "tag2"]
    
    # Fields dict
    mock_note.__getitem__.side_effect = lambda key: {
        "Front": "Question?",
        "Back": "Answer.",
        "Answer": "Direct Answer",
        "Explanation": "Explanation text",
        "Card ID": "c-123",
        "Version ID": "v-1"
    }.get(key)
    
    # Mock model (notetype)
    mock_model = {
        "name": "Anki Concursos Basic",
        "type": 0, # Basic
        "flds": [
            {"name": "Front"}, {"name": "Back"}, {"name": "Answer"}, 
            {"name": "Explanation"}, {"name": "Card ID"}, {"name": "Version ID"}
        ],
        "tmpls": [
            {"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{Back}}"}
        ],
        "css": ".card { color: red; }"
    }
    mock_note.model.return_value = mock_model
    mock_mw.col.get_note.return_value = mock_note
    
    payload = exporter.export_deck(1)
    
    assert payload["deck_name"] == "Direito Constitucional"
    assert payload["publish_release"] is True
    assert len(payload["templates"]) == 1
    assert payload["templates"][0]["template_name"] == "Card 1"
    assert payload["templates"][0]["note_type"] == "Anki Concursos Basic"
    assert payload["templates"][0]["card_kind"] == "basic"
    assert payload["templates"][0]["fields"] == ["Front", "Back", "Answer", "Explanation"]
    assert payload["templates"][0]["styling_css"] == ".card { color: red; }"
    
    assert len(payload["notes"]) == 1
    assert payload["notes"][0]["note_type"] == "Anki Concursos Basic"
    assert payload["notes"][0]["card_kind"] == "basic"
    assert payload["notes"][0]["fields"] == {
        "Front": "Question?",
        "Back": "Answer.",
        "Answer": "Direct Answer",
        "Explanation": "Explanation text"
    }
    assert payload["notes"][0]["tags"] == ["tag1", "tag2"]

@patch("anki_concursos.services.deck_exporter.mw")
def test_export_deck_cloze_validation_failure(mock_mw):
    exporter = DeckExporter()
    mock_mw.col.decks.get.return_value = {"name": "Direito Cloze"}
    mock_mw.col.find_notes.return_value = [1002]
    
    mock_note = MagicMock()
    mock_note.tags = []
    # No cloze markup in Text field
    mock_note.__getitem__.side_effect = lambda key: {
        "Text": "This is a plain text without cloze markup.",
        "Extra": "Some extra info"
    }.get(key)
    
    mock_model = {
        "name": "Anki Concursos Cloze",
        "type": 1, # Cloze
        "flds": [{"name": "Text"}, {"name": "Extra"}],
        "tmpls": [{"name": "Cloze", "qfmt": "{{cloze:Text}}", "afmt": "{{cloze:Text}}"}],
        "css": ""
    }
    mock_note.model.return_value = mock_model
    mock_mw.col.get_note.return_value = mock_note
    
    with pytest.raises(ValueError) as exc_info:
        exporter.export_deck(1)
        
    assert "não contém a marcação de lacuna necessária" in str(exc_info.value)


@patch("anki_concursos.services.deck_exporter.mw")
def test_export_deck_cloze_multi_field_mapping(mock_mw):
    exporter = DeckExporter()
    mock_mw.col.decks.get.return_value = {"name": "Getting Started"}
    mock_mw.col.find_notes.return_value = [1003]
    
    mock_note = MagicMock()
    mock_note.tags = ["getting_started"]
    
    # Lesson is first but Cloze has the markup
    mock_note.__getitem__.side_effect = lambda key: {
        "Lesson": "In Anki, we add and edit notes rather than cards...",
        "Cloze": "Anki will create {{c1::two::#}} cards from the note above.",
        "Extra": "Extra info",
        "Deep Dive": "Deep dive link",
        "ankihub_id": "ah-1"
    }.get(key)
    
    mock_model = {
        "name": "Getting Started Cloze",
        "type": 1, # Cloze
        "flds": [
            {"name": "Lesson"}, {"name": "Cloze"}, {"name": "Extra"}, 
            {"name": "Deep Dive"}, {"name": "ankihub_id"}
        ],
        "tmpls": [{"name": "Cloze", "qfmt": "{{cloze:Cloze}}", "afmt": "{{cloze:Cloze}}"}],
        "css": ""
    }
    mock_note.model.return_value = mock_model
    mock_mw.col.get_note.return_value = mock_note
    
    payload = exporter.export_deck(1)
    
    # Assert Cloze mapped to front_text, Extra to back_text
    assert payload["deck_name"] == "Getting Started"
    assert len(payload["templates"]) == 1
    assert payload["templates"][0]["field_mapping"]["Cloze"] == "front_text"
    assert payload["templates"][0]["field_mapping"]["Extra"] == "back_text"
    
    # Assert fields parsed
    assert payload["notes"][0]["fields"]["Lesson"] == "In Anki, we add and edit notes rather than cards..."
    assert payload["notes"][0]["fields"]["Cloze"] == "Anki will create {{c1::two::#}} cards from the note above."
