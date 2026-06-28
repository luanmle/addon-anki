from anki_concursos.services.suggestions import (
    diff_preview_text,
    filter_fields_for_suggestion,
    note_fields_for_suggestion,
)


class FakeNote:
    def __init__(self):
        self._fields = {
            "Public ID": "p1",
            "Card ID": "c1",
            "Version ID": "v1",
            "Front": "Pergunta",
            "Back": "Resposta",
        }

    def keys(self):
        return self._fields.keys()

    def __getitem__(self, field_name):
        return self._fields[field_name]


def test_note_fields_for_suggestion_omits_sync_metadata():
    assert note_fields_for_suggestion(FakeNote()) == {
        "Front": "Pergunta",
        "Back": "Resposta",
    }


def test_filter_fields_for_suggestion_keeps_selected_fields_only():
    assert filter_fields_for_suggestion(
        {"Front": "Pergunta", "Back": "Resposta"},
        ["Back"],
    ) == {"Back": "Resposta"}


def test_diff_preview_text_marks_changed_and_unchanged_fields():
    text = diff_preview_text(
        {"Front": "Original", "Back": "Igual"},
        {"Front": "Novo", "Back": "Igual"},
    )

    assert "Front (alterado)" in text
    assert "Antes: Original" in text
    assert "Depois: Novo" in text
    assert "Back (sem alteração)" in text
