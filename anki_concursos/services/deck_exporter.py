import logging
import re
from typing import Any, Dict, List

from aqt import mw

logger = logging.getLogger("anki_concursos.services.exporter")


class DeckExporter:
    ALLOWED_TARGET_FIELDS = {
        "front_text",
        "back_text",
        "answer_text",
        "explanation_text",
    }

    def export_deck(self, anki_deck_id: int) -> Dict[str, Any]:
        """Export a complete Anki deck into the platform's JSON package structure."""
        deck = mw.col.decks.get(anki_deck_id)
        if not deck:
            raise ValueError(f"Baralho ID {anki_deck_id} não encontrado no Anki.")

        deck_name = deck["name"]
        escaped_deck_name = deck_name.replace('"', '\\"')
        note_ids = mw.col.find_notes(f'deck:"{escaped_deck_name}"')

        if not note_ids:
            raise ValueError(f"O baralho '{deck_name}' está vazio ou não contém notas.")

        addon_config = self._load_config()
        upload_mappings = self._load_upload_mappings(addon_config)

        notes_payload: list[dict[str, Any]] = []
        templates_dict: dict[tuple[str, str], dict[str, Any]] = {}

        metadata_fields = {"Public ID", "Card ID", "Version ID"}
        cloze_pattern = re.compile(r"\{\{c\d+::.*?\}\}")

        for note_id in note_ids:
            note = mw.col.get_note(note_id)
            notetype = note.model()
            if not notetype:
                continue

            note_type_name = notetype["name"]
            card_kind = "cloze" if notetype["type"] == 1 else "basic"
            fields_list = [
                f["name"]
                for f in notetype["flds"]
                if f["name"] not in metadata_fields
            ]
            note_fields = {field_name: note[field_name] for field_name in fields_list}
            tmpls = notetype.get("tmpls", [])
            if not tmpls:
                raise ValueError(
                    f"O modelo de nota '{note_type_name}' não possui nenhum template de cartão definido."
                )
            field_mapping = self._resolve_field_mapping(
                note_type_name=note_type_name,
                note_fields=note_fields,
                upload_mappings=upload_mappings,
                templates=tmpls,
            )
            self._validate_mapping(
                note_id=note_id,
                note_type_name=note_type_name,
                card_kind=card_kind,
                note_fields=note_fields,
                field_mapping=field_mapping,
                cloze_pattern=cloze_pattern,
            )

            source_note_id = str(getattr(note, "id", note_id))
            source_note_guid = getattr(note, "guid", None)
            source_deck_path = deck_name

            for tmpl in tmpls:
                tmpl_name = tmpl["name"]
                key = (note_type_name, tmpl_name)
                if key not in templates_dict:
                    templates_dict[key] = {
                        "template_name": tmpl_name,
                        "note_type": note_type_name,
                        "card_kind": card_kind,
                        "fields": fields_list,
                        "field_mapping": field_mapping,
                        "front_html": tmpl["qfmt"],
                        "back_html": tmpl["afmt"],
                        "styling_css": notetype.get("css", ""),
                    }
                notes_payload.append(
                    {
                        "note_type": note_type_name,
                        "template_name": tmpl_name,
                        "card_kind": card_kind,
                        "source_note_id": source_note_id,
                        "source_note_guid": source_note_guid,
                        "source_deck_path": source_deck_path,
                        "fields": note_fields,
                        "tags": list(note.tags),
                    }
                )

        return {
            "deck_name": deck_name,
            "description": f"Pacote completo exportado do Anki - {deck_name}",
            "source_name": "addon",
            "publish_release": True,
            "templates": list(templates_dict.values()),
            "notes": notes_payload,
        }

    def _load_config(self) -> Dict[str, Any]:
        if not mw or not getattr(mw, "addonManager", None):
            return {}
        addon_folder = __name__.split(".")[0]
        return mw.addonManager.getConfig(addon_folder) or {}

    def _load_upload_mappings(self, config: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        raw_mappings = config.get("upload_field_mappings", {})
        if not isinstance(raw_mappings, dict):
            raise ValueError(
                "A configuração upload_field_mappings deve ser um objeto JSON com mapeamentos explícitos."
            )

        normalized: Dict[str, Dict[str, str]] = {}
        for note_type_name, mapping in raw_mappings.items():
            if isinstance(mapping, dict) and "field_mapping" in mapping and isinstance(mapping["field_mapping"], dict):
                mapping = mapping["field_mapping"]
            if not isinstance(mapping, dict):
                raise ValueError(
                    f"O mapeamento do note type '{note_type_name}' deve ser um objeto JSON."
                )
            normalized[note_type_name.lower()] = {
                str(source).strip(): str(target).strip()
                for source, target in mapping.items()
                if str(source).strip() and str(target).strip()
            }
        return normalized

    @staticmethod
    def _normalize_note_type_name(name: str) -> str:
        cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", name or "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned.lower()

    def _find_upload_mapping(
        self,
        note_type_name: str,
        upload_mappings: Dict[str, Dict[str, str]],
    ) -> Dict[str, str] | None:
        if not note_type_name:
            return None

        normalized_note_type = self._normalize_note_type_name(note_type_name)
        if normalized_note_type in upload_mappings:
            return upload_mappings[normalized_note_type]

        exact_lower = note_type_name.strip().lower()
        if exact_lower in upload_mappings:
            return upload_mappings[exact_lower]

        for key, mapping in upload_mappings.items():
            normalized_key = self._normalize_note_type_name(key)
            if normalized_key == normalized_note_type:
                return mapping

        for key, mapping in upload_mappings.items():
            normalized_key = self._normalize_note_type_name(key)
            if normalized_note_type.startswith(normalized_key) or normalized_key.startswith(normalized_note_type):
                return mapping

        return None

    def _resolve_field_mapping(
        self,
        *,
        note_type_name: str,
        note_fields: Dict[str, str],
        upload_mappings: Dict[str, Dict[str, str]],
        templates: list[Dict[str, Any]],
    ) -> Dict[str, str]:
        mapping = self._find_upload_mapping(note_type_name, upload_mappings)
        if mapping is None:
            mapping = self._derive_field_mapping_from_templates(
                templates=templates,
                note_fields=note_fields,
            )

        resolved: Dict[str, str] = {}
        for source_field, target_field in mapping.items():
            if target_field not in self.ALLOWED_TARGET_FIELDS:
                raise ValueError(
                    f"Target inválido '{target_field}' no mapeamento de '{note_type_name}'. "
                    f"Use apenas: {sorted(self.ALLOWED_TARGET_FIELDS)}"
                )

            matching_source = self._find_source_field(source_field, note_fields)
            if matching_source is None:
                raise ValueError(
                    f"Campo '{source_field}' não encontrado na nota do tipo '{note_type_name}'."
                )
            resolved[matching_source] = target_field

        if "front_text" not in set(resolved.values()):
            raise ValueError(
                f"Não foi possível determinar um campo para 'front_text' no note type '{note_type_name}'. "
                "Defina upload_field_mappings ou ajuste o template do Anki."
            )

        return resolved

    def _derive_field_mapping_from_templates(
        self,
        *,
        templates: list[Dict[str, Any]],
        note_fields: Dict[str, str],
    ) -> Dict[str, str]:
        ordered_sources: list[str] = []
        seen: set[str] = set()

        for template in templates:
            for html_key in ("qfmt", "afmt"):
                for source in self._extract_template_sources(template.get(html_key, "")):
                    matched = self._find_source_field(source, note_fields)
                    if matched and matched not in seen:
                        seen.add(matched)
                        ordered_sources.append(matched)

        if not ordered_sources:
            ordered_sources = [
                field_name
                for field_name, value in note_fields.items()
                if isinstance(value, str) and value.strip()
            ]

        mapping: Dict[str, str] = {}
        targets = ["front_text", "back_text", "answer_text", "explanation_text"]
        for source, target in zip(ordered_sources, targets, strict=False):
            mapping[source] = target
        return mapping

    @staticmethod
    def _extract_template_sources(template_html: str) -> list[str]:
        sources: list[str] = []
        if not template_html:
            return sources

        pattern = re.compile(r"\{\{\s*(?:cloze:)?([^{}|}]+?)\s*\}\}", re.IGNORECASE)
        for match in pattern.finditer(template_html):
            raw_source = match.group(1).strip()
            if not raw_source:
                continue
            if raw_source.lower() in {"frontside"}:
                continue
            if raw_source not in sources:
                sources.append(raw_source)
        return sources

    @staticmethod
    def _find_source_field(source_field: str, note_fields: Dict[str, str]) -> str | None:
        if source_field in note_fields:
            return source_field
        lowered = source_field.lower()
        for candidate in note_fields:
            if candidate.lower() == lowered:
                return candidate
        return None

    def _validate_mapping(
        self,
        *,
        note_id: int,
        note_type_name: str,
        card_kind: str,
        note_fields: Dict[str, str],
        field_mapping: Dict[str, str],
        cloze_pattern: re.Pattern[str],
    ) -> None:
        mapped_targets = set(field_mapping.values())
        if "front_text" not in mapped_targets:
            raise ValueError(
                f"A nota ID {note_id} ({note_type_name}) precisa mapear explicitamente um campo para 'front_text'."
            )

        if card_kind == "cloze":
            front_source = next(
                (source for source, target in field_mapping.items() if target == "front_text"),
                None,
            )
            front_value = note_fields.get(front_source, "") if front_source else ""
            if not isinstance(front_value, str) or not cloze_pattern.search(front_value):
                raise ValueError(
                    f"A nota de omissão (cloze) ID {note_id} precisa ter a marcação {{c1::...}} "
                    f"no campo mapeado para front_text ('{front_source}')."
                )
