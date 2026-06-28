from types import SimpleNamespace

from anki_concursos.sync.fields import (
    field_mapping_for_change,
    note_fields_from_change,
    protected_fields_for_change,
)
from anki_concursos.services.note_manager import NoteManager


def _manifest():
    return SimpleNamespace(
        supported_note_types={
            "basic": {"field_mapping": {"Front": "front_text", "Back": "back_text"}}
        },
        templates=[],
    )


def test_field_mapping_skipped_when_native_flag_true():
    change = SimpleNamespace(
        fields={"Frente": "x"}, native=True, note_type="X", template_name=None
    )
    assert field_mapping_for_change(change, _manifest(), "basic") is None


def test_field_mapping_returned_when_native_flag_false():
    change = SimpleNamespace(
        fields={"Front": "x"}, native=False, note_type="X", template_name=None
    )
    assert field_mapping_for_change(change, _manifest(), "basic") == {
        "Front": "front_text",
        "Back": "back_text",
    }


def test_field_mapping_falls_back_to_heuristic_when_flag_absent():
    # No `native` attr (older server): no manifest templates => treated legacy.
    change = SimpleNamespace(
        fields={"Front": "x"}, note_type="X", template_name=None
    )
    assert field_mapping_for_change(change, _manifest(), "basic") == {
        "Front": "front_text",
        "Back": "back_text",
    }


def test_field_mapping_none_for_empty_fields():
    change = SimpleNamespace(fields=None, native=False)
    assert field_mapping_for_change(change, _manifest(), "basic") is None


def test_note_fields_from_change_maps_legacy_keys_to_note_fields():
    assert note_fields_from_change(
        {"front_text": "Pergunta", "back_text": "Resposta", "Extra": "E"},
        {"Front": "front_text", "Back": "back_text"},
    ) == {
        "Front": "Pergunta",
        "Back": "Resposta",
        "Extra": "E",
    }


class _FakeNote(dict):
    """Minimal stand-in for an Anki note (dict of field name -> value)."""


def test_apply_fields_keeps_fields_omitted_by_mapping():
    note = _FakeNote({"Front": "", "Back": "", "Answer": "", "Explanation": ""})
    fields = {"Front": "f", "Back": "b", "Answer": "a", "Explanation": "e", "Junk": "z"}
    # Mapping omits Answer/Explanation.
    mapping = {"Front": "front_text", "Back": "back_text"}

    NoteManager()._apply_fields(note, fields, mapping)

    assert note["Front"] == "f"
    assert note["Back"] == "b"
    # Previously dropped — must now be preserved.
    assert note["Answer"] == "a"
    assert note["Explanation"] == "e"
    # A key with no matching note field is ignored, not crashed on.
    assert "Junk" not in note


def test_apply_fields_preserves_protected_fields():
    note = _FakeNote({"Front": "local", "Back": "old"})

    NoteManager()._apply_fields(
        note,
        {"front_text": "remote", "back_text": "new"},
        {"Front": "front_text", "Back": "back_text"},
        protected_fields={"Front"},
    )

    assert note["Front"] == "local"
    assert note["Back"] == "new"


def test_protected_fields_can_come_from_template_or_legacy_mapping():
    manifest = SimpleNamespace(
        supported_note_types={
            "basic": {
                "field_mapping": {"Front": "front_text", "Back": "back_text"},
                "protected_fields": ["front_text"],
            }
        },
        templates=[
            {
                "note_type": "nt",
                "template_name": "Card 1",
                "protected_fields": ["Back"],
            }
        ],
    )
    change = SimpleNamespace(
        fields={"front_text": "remote", "back_text": "new"},
        note_type="nt",
        template_name="Card 1",
        template=None,
    )

    assert protected_fields_for_change(
        change,
        manifest,
        "basic",
        {"Front": "front_text", "Back": "back_text"},
    ) == {"front_text", "Front", "Back"}
