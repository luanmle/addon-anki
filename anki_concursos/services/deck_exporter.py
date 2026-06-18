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
            field_mapping = self._resolve_field_mapping(
                note_type_name=note_type_name,
                note_fields=note_fields,
                upload_mappings=upload_mappings,
            )
            self._validate_mapping(
                note_id=note_id,
                note_type_name=note_type_name,
                card_kind=card_kind,
                note_fields=note_fields,
                field_mapping=field_mapping,
                cloze_pattern=cloze_pattern,
            )

            tmpls = notetype.get("tmpls", [])
            if not tmpls:
                raise ValueError(
                    f"O modelo de nota '{note_type_name}' não possui nenhum template de cartão definido."
                )

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
                    "card_kind": card_kind,
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

    def _resolve_field_mapping(
        self,
        *,
        note_type_name: str,
        note_fields: Dict[str, str],
        upload_mappings: Dict[str, Dict[str, str]],
    ) -> Dict[str, str]:
        mapping = upload_mappings.get(note_type_name.lower())
        if mapping is None:
            raise ValueError(
                f"Não há mapeamento explícito para o note type '{note_type_name}'. "
                "Adicione upload_field_mappings no config.json do add-on."
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

        return resolved

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
