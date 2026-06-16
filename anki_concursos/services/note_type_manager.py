import logging
from typing import List

from aqt import mw
from anki.models import NotetypeDict

logger = logging.getLogger("anki_concursos.services.notetype")

class NoteTypeManager:
    def ensure_note_type(self, manifest) -> None:
        """Ensure note types defined in the manifest exist in Anki."""
        # The manifest has supported_note_types: Dict[str, Dict]
        for kind, nt_def in manifest.supported_note_types.items():
            nt_name = nt_def["note_type"]
            fields = nt_def["fields"]
            
            # Check if it already exists
            existing = mw.col.models.by_name(nt_name)
            if existing:
                self._verify_fields(existing, fields)
                continue
                
            self._create_note_type(nt_name, kind, fields)

    def _verify_fields(self, notetype: NotetypeDict, required_fields: List[str]) -> None:
        # We need the hidden metadata fields too
        all_fields = ["Public ID", "Card ID", "Version ID"] + required_fields
        existing_fields = [f["name"] for f in notetype["flds"]]
        
        missing = [f for f in all_fields if f not in existing_fields]
        if missing:
            logger.info(f"Note type {notetype['name']} missing fields: {missing}. Adding them.")
            for f in missing:
                field = mw.col.models.new_field(f)
                mw.col.models.add_field(notetype, field)
            mw.col.models.save(notetype)

    def _create_note_type(self, name: str, kind: str, fields: List[str]) -> None:
        logger.info(f"Creating note type {name} ({kind})")
        
        all_fields = ["Public ID", "Card ID", "Version ID"] + fields
        
        if kind == "cloze":
            base = mw.col.models.by_name("Cloze")
            if not base:
                nt = mw.col.models.new(name)
                nt["type"] = 1 # 1 is cloze
            else:
                nt = mw.col.models.copy(base)
                nt["name"] = name
        else:
            base = mw.col.models.by_name("Basic")
            if not base:
                nt = mw.col.models.new(name)
            else:
                nt = mw.col.models.copy(base)
                nt["name"] = name
                
        # Remove existing fields safely
        nt["flds"] = []
        
        # Add new fields
        for f in all_fields:
            field = mw.col.models.new_field(f)
            mw.col.models.add_field(nt, field)
            
        # Ensure templates
        if kind == "basic":
            nt["tmpls"] = []
            tmpl = mw.col.models.new_template("Card 1")
            tmpl["qfmt"] = "{{Front}}"
            tmpl["afmt"] = "{{FrontSide}}\\n\\n<hr id=answer>\\n\\n{{Back}}\\n\\n<div class='answer'>{{Answer}}</div>\\n\\n<div class='explanation'>{{Explanation}}</div>"
            mw.col.models.add_template(nt, tmpl)
            
        elif kind == "cloze" and not base:
            nt["tmpls"] = []
            tmpl = mw.col.models.new_template("Cloze")
            tmpl["qfmt"] = "{{cloze:Text}}"
            tmpl["afmt"] = "{{cloze:Text}}\\n\\n<br>\\n{{Extra}}\\n\\n<div class='answer'>{{Answer}}</div>\\n\\n<div class='explanation'>{{Explanation}}</div>"
            mw.col.models.add_template(nt, tmpl)
            
        # Add minimal CSS
        nt["css"] += "\\n.answer { color: #28a745; margin-top: 15px; font-weight: bold; }\\n.explanation { margin-top: 15px; font-style: italic; background-color: #f8f9fa; padding: 10px; border-radius: 5px; }\\n"
        
        mw.col.models.add_dict(nt)
