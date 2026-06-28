from typing import Any, Dict, Iterable


METADATA_FIELDS = {"Public ID", "Card ID", "Version ID"}


def note_fields_for_suggestion(note: Any) -> Dict[str, str]:
    return {
        field_name: note[field_name]
        for field_name in note.keys()
        if field_name not in METADATA_FIELDS
    }


def filter_fields_for_suggestion(
    fields: Dict[str, str],
    selected_field_names: Iterable[str],
) -> Dict[str, str]:
    selected = set(selected_field_names)
    return {
        field_name: value
        for field_name, value in fields.items()
        if field_name in selected
    }


def diff_preview_text(
    original_fields: Dict[str, str],
    selected_fields: Dict[str, str],
) -> str:
    lines: list[str] = []
    for field_name, new_value in selected_fields.items():
        old_value = original_fields.get(field_name, "")
        status = "alterado" if old_value != new_value else "sem alteração"
        lines.extend(
            [
                f"{field_name} ({status})",
                f"Antes: {_one_line(old_value)}",
                f"Depois: {_one_line(new_value)}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _one_line(value: str) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= 180 else f"{text[:177]}..."
