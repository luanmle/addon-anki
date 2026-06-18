import logging
import re
from typing import Dict, Any, List

from aqt import mw

logger = logging.getLogger("anki_concursos.services.exporter")

class DeckExporter:
    def export_deck(self, anki_deck_id: int) -> Dict[str, Any]:
        """Export a complete Anki deck into the platform's JSON package structure."""
        deck = mw.col.decks.get(anki_deck_id)
        if not deck:
            raise ValueError(f"Baralho ID {anki_deck_id} não encontrado no Anki.")
            
        deck_name = deck["name"]
        
        # Get all note IDs for cards in this deck (including subdecks)
        escaped_deck_name = deck_name.replace('"', '\\"')
        note_ids = mw.col.find_notes(f'deck:"{escaped_deck_name}"')
        
        if not note_ids:
            raise ValueError(f"O baralho '{deck_name}' está vazio ou não contém notas.")
            
        notes_payload = []
        templates_dict = {} # (note_type_name, template_name) -> template_data
        
        metadata_fields = {"Public ID", "Card ID", "Version ID"}
        cloze_pattern = re.compile(r"\{\{c\d+::.*?\}\}")
        
        for note_id in note_ids:
            note = mw.col.get_note(note_id)
            notetype = note.model()
            if not notetype:
                continue
                
            note_type_name = notetype["name"]
            card_kind = "cloze" if notetype["type"] == 1 else "basic"
            
            # 1. Get filtered fields list
            fields_list = [f["name"] for f in notetype["flds"] if f["name"] not in metadata_fields]
            
            # Resolve field mapping
            field_mapping = self._resolve_field_mapping(fields_list, card_kind)
            
            # Check fields validation
            mapped_values = set(field_mapping.values())
            if "front_text" not in mapped_values:
                raise ValueError(f"A nota ID {note_id} ({note_type_name}) não possui campo mapeável para 'front_text'.")
            if "back_text" not in mapped_values and card_kind == "basic":
                raise ValueError(f"A nota ID {note_id} ({note_type_name}) não possui campo mapeável para 'back_text'.")
                
            # 2. Extract note fields
            note_fields = {}
            for f_name in fields_list:
                note_fields[f_name] = note[f_name]
                
            # Validate Cloze markup if needed
            if card_kind == "cloze":
                front_field = None
                for f, canonical in field_mapping.items():
                    if canonical == "front_text":
                        front_field = f
                        break
                if front_field:
                    text_val = note_fields.get(front_field, "")
                    if not cloze_pattern.search(text_val):
                        raise ValueError(
                            f"A nota de omissão (cloze) ID {note_id} no campo '{front_field}' "
                            f"não contém a marcação de lacuna necessária (ex: {{{{c1::texto}}}})."
                        )
            
            # 3. Add to templates list if not already there
            tmpls = notetype.get("tmpls", [])
            if not tmpls:
                raise ValueError(f"O modelo de nota '{note_type_name}' não possui nenhum template de cartão definido.")
                
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
                        "styling_css": notetype.get("css", "")
                    }
                    
            # 4. Add note
            notes_payload.append({
                "note_type": note_type_name,
                "card_kind": card_kind,
                "fields": note_fields,
                "tags": note.tags
            })
            
        templates_payload = list(templates_dict.values())
        
        return {
            "deck_name": deck_name,
            "description": f"Pacote completo exportado do Anki - {deck_name}",
            "source_name": "addon",
            "publish_release": True,
            "templates": templates_payload,
            "notes": notes_payload
        }
        
    def _resolve_field_mapping(self, fields: List[str], card_kind: str) -> Dict[str, str]:
        mapping = {}
        f_lower = {f.lower(): f for f in fields}
        
        if card_kind == "cloze":
            if "text" in f_lower:
                mapping[f_lower["text"]] = "front_text"
            elif "texto" in f_lower:
                mapping[f_lower["texto"]] = "front_text"
                
            if "extra" in f_lower:
                mapping[f_lower["extra"]] = "back_text"
        else:
            # Basic
            for k in ["front", "frente", "questao", "questão", "pergunta"]:
                if k in f_lower:
                    mapping[f_lower[k]] = "front_text"
                    break
                    
            for k in ["back", "verso", "resposta"]:
                if k in f_lower:
                    mapping[f_lower[k]] = "back_text"
                    break
                    
            for k in ["answer", "gabarito"]:
                if k in f_lower:
                    mapping[f_lower[k]] = "answer_text"
                    break
                    
            for k in ["explanation", "explicacao", "explicação", "comentario", "comentário"]:
                if k in f_lower:
                    mapping[f_lower[k]] = "explanation_text"
                    break
                    
        # Fallback: if we still don't have front_text and back_text, map positional ones
        mapped_vals = set(mapping.values())
        if "front_text" not in mapped_vals and len(fields) > 0:
            for f in fields:
                if f not in mapping:
                    mapping[f] = "front_text"
                    break
        if "back_text" not in mapped_vals and len(fields) > 0:
            for f in fields:
                if f not in mapping and mapping.get(f) != "front_text":
                    mapping[f] = "back_text"
                    break
                    
        return mapping
