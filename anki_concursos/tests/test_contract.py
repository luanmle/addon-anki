from types import SimpleNamespace

from anki_concursos.sync.fields import field_mapping_for_change
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
