from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional


def field_mapping_for_change(
    change: Any,
    manifest: Any,
    kind: str,
) -> Optional[Dict[str, str]]:
    """Return the legacy field mapping only when a change is not native Anki data."""
    fields = getattr(change, "fields", None)
    if not isinstance(fields, dict) or not fields:
        return None

    native_flag = getattr(change, "native", None)
    if isinstance(native_flag, bool):
        # Trust the explicit server contract when present.
        if native_flag:
            return None
    elif _uses_native_fields(change, manifest, fields):
        # Backward compat: older servers omit the flag, infer from shape.
        return None

    supported_note_types = getattr(manifest, "supported_note_types", {}) or {}
    if not isinstance(supported_note_types, dict):
        return None

    note_type_config = supported_note_types.get(kind, {})
    if not isinstance(note_type_config, dict):
        return None

    field_mapping = note_type_config.get("field_mapping")
    return field_mapping if isinstance(field_mapping, dict) else None


def _uses_native_fields(change: Any, manifest: Any, fields: Any) -> bool:
    if not isinstance(fields, dict) or not fields:
        return False

    change_template = _template_data(getattr(change, "template", None))
    if change_template is not None:
        return True

    matching_templates = _matching_manifest_templates(change, manifest)
    if not matching_templates:
        return False

    field_names = set(fields)
    return any(field_names.issubset(set(template.get("fields", []))) for template in matching_templates)


def _matching_manifest_templates(change: Any, manifest: Any) -> list[Dict[str, Any]]:
    templates = [
        template
        for template in (
            _template_data(raw_template)
            for raw_template in (getattr(manifest, "templates", None) or [])
        )
        if template is not None
    ]
    if not templates:
        return []

    note_type = _string_attr(change, "note_type")
    template_name = _string_attr(change, "template_name")

    matches = templates
    if note_type:
        matches = [template for template in matches if template.get("note_type") == note_type]
    if template_name:
        named_matches = [
            template for template in matches if template.get("template_name") == template_name
        ]
        if named_matches:
            matches = named_matches

    return matches


def _template_data(template: Any) -> Optional[Dict[str, Any]]:
    if isinstance(template, dict):
        return template
    if is_dataclass(template):
        return asdict(template)
    return None


def _string_attr(obj: Any, name: str) -> Optional[str]:
    value = getattr(obj, name, None)
    return value if isinstance(value, str) else None
