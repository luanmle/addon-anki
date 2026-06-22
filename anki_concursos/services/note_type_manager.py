import logging
from collections import defaultdict
from typing import Dict, List, Optional

from aqt import mw
from anki.models import NotetypeDict

logger = logging.getLogger("anki_concursos.services.notetype")

class NoteTypeManager:
    def ensure_note_type(self, manifest) -> None:
        """Ensure note types defined in the manifest exist in Anki."""
        template_groups = defaultdict(set)
        templates = [self._template_as_dict(template) for template in getattr(manifest, "templates", [])]
        if templates:
            for template in templates:
                nt_name = template.get("note_type")
                if not nt_name:
                    continue
                for field_name in template.get("fields", []):
                    if field_name:
                        template_groups[nt_name].add(field_name)

        if template_groups:
            for nt_name, fields in template_groups.items():
                existing = mw.col.models.by_name(nt_name)
                field_list = sorted(fields, key=str.lower)
                if existing:
                    self._verify_fields(existing, field_list)
                    continue
                kind = "cloze" if any(
                    (template.get("card_kind") == "cloze")
                    for template in templates
                    if template.get("note_type") == nt_name
                ) else "basic"
                # Use the server's HTML so the template only references fields
                # that actually exist in this note type.
                nt_tmpls = [t for t in templates if t.get("note_type") == nt_name]
                first = nt_tmpls[0] if nt_tmpls else {}
                self._create_note_type(
                    nt_name, kind, field_list,
                    template_name=first.get("template_name") or None,
                    front_html=first.get("front_html") or None,
                    back_html=first.get("back_html") or None,
                    styling_css=first.get("styling_css") or None,
                )
            return

        # Fallback for legacy manifests
        for kind, nt_def in manifest.supported_note_types.items():
            nt_name = nt_def["note_type"]
            fields = nt_def["fields"]
            
            # Check if it already exists
            existing = mw.col.models.by_name(nt_name)
            if existing:
                self._verify_fields(existing, fields)
                continue
                
            self._create_note_type(nt_name, kind, fields)

    @staticmethod
    def _template_as_dict(template) -> dict:
        if isinstance(template, dict):
            return template
        if hasattr(template, "__dict__"):
            return dict(template.__dict__)
        return {
            key: getattr(template, key)
            for key in ("template_name", "note_type", "card_kind", "fields", "field_mapping", "front_html", "back_html", "styling_css")
            if hasattr(template, key)
        }

    def apply_template_versions(self, versions: List) -> int:
        """Apply template version changes from GET /addon/decks/{id}/templates/sync.

        Returns count of Anki note types actually modified or created.
        """
        updated = 0
        for version in versions:
            v = self._template_as_dict(version)
            nt_name = v.get("note_type")
            if not nt_name:
                continue
            card_kind = str(v.get("card_kind", "basic"))
            fields: List[str] = list(v.get("fields") or [])
            template_name: str = v.get("template_name") or "Card 1"
            front_html: str = v.get("front_html") or ""
            back_html: str = v.get("back_html") or ""
            styling_css: str = v.get("styling_css") or ""

            notetype = mw.col.models.by_name(nt_name)
            if notetype is None:
                self._create_note_type(
                    nt_name, card_kind, fields,
                    template_name=template_name,
                    front_html=front_html or None,
                    back_html=back_html or None,
                    styling_css=styling_css or None,
                )
                updated += 1
                logger.info(f"Created note type '{nt_name}' from template version.")
            else:
                changed = self._ensure_fields(notetype, fields)
                changed |= self._update_anki_template(notetype, template_name, front_html, back_html)
                if styling_css and notetype.get("css", "") != styling_css:
                    notetype["css"] = styling_css
                    changed = True
                if changed:
                    mw.col.models.save(notetype)
                    updated += 1
                    logger.info(f"Updated note type '{nt_name}' from template version.")
        return updated

    def _ensure_fields(self, notetype: NotetypeDict, required_fields: List[str]) -> bool:
        """Add missing fields (including metadata fields). Returns True if changed."""
        all_fields = ["Public ID", "Card ID", "Version ID"] + list(required_fields)
        existing = {f["name"] for f in notetype["flds"]}
        missing = [f for f in all_fields if f not in existing]
        if not missing:
            return False
        logger.info(f"Note type '{notetype['name']}' missing fields: {missing}. Adding.")
        for fname in missing:
            field = mw.col.models.new_field(fname)
            mw.col.models.add_field(notetype, field)
        return True

    def _update_anki_template(
        self, notetype: NotetypeDict, template_name: str, front_html: str, back_html: str
    ) -> bool:
        """Update qfmt/afmt of the named card template. Returns True if changed."""
        if not front_html and not back_html:
            return False
        tmpls = notetype.get("tmpls", [])
        tmpl = next((t for t in tmpls if t["name"] == template_name), None)
        if tmpl is None and tmpls:
            tmpl = tmpls[0]
        if tmpl is None:
            return False
        changed = False
        if front_html and tmpl.get("qfmt") != front_html:
            tmpl["qfmt"] = front_html
            changed = True
        if back_html and tmpl.get("afmt") != back_html:
            tmpl["afmt"] = back_html
            changed = True
        return changed

    def _verify_fields(self, notetype: NotetypeDict, required_fields: List[str]) -> None:
        if self._ensure_fields(notetype, required_fields):
            mw.col.models.save(notetype)

    def _create_note_type(
        self,
        name: str,
        kind: str,
        fields: List[str],
        template_name: Optional[str] = None,
        front_html: Optional[str] = None,
        back_html: Optional[str] = None,
        styling_css: Optional[str] = None,
    ) -> None:
        logger.info(f"Creating note type {name} ({kind})")

        all_fields = ["Public ID", "Card ID", "Version ID"] + fields

        if kind == "cloze":
            base = mw.col.models.by_name("Cloze")
            if not base:
                nt = mw.col.models.new(name)
                nt["type"] = 1
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

        nt["flds"] = []
        for f in all_fields:
            field = mw.col.models.new_field(f)
            mw.col.models.add_field(nt, field)

        if kind == "basic":
            nt["tmpls"] = []
            tmpl = mw.col.models.new_template(template_name or "Card 1")
            tmpl["qfmt"] = front_html if front_html else "{{Front}}"
            tmpl["afmt"] = back_html if back_html else "{{FrontSide}}\\n\\n<hr id=answer>\\n\\n{{Back}}\\n\\n<div class='answer'>{{Answer}}</div>\\n\\n<div class='explanation'>{{Explanation}}</div>"
            mw.col.models.add_template(nt, tmpl)
        elif kind == "cloze" and not base:
            nt["tmpls"] = []
            tmpl = mw.col.models.new_template(template_name or "Cloze")
            tmpl["qfmt"] = front_html if front_html else "{{cloze:Text}}"
            tmpl["afmt"] = back_html if back_html else "{{cloze:Text}}\\n\\n<br>\\n{{Extra}}\\n\\n<div class='answer'>{{Answer}}</div>\\n\\n<div class='explanation'>{{Explanation}}</div>"
            mw.col.models.add_template(nt, tmpl)
        elif kind == "cloze" and base and (front_html or back_html):
            # Update the copied template HTML with server values
            for tmpl in nt.get("tmpls", []):
                if front_html:
                    tmpl["qfmt"] = front_html
                if back_html:
                    tmpl["afmt"] = back_html

        if styling_css:
            nt["css"] = styling_css
        else:
            nt["css"] += "\\n.answer { color: #28a745; margin-top: 15px; font-weight: bold; }\\n.explanation { margin-top: 15px; font-style: italic; background-color: #f8f9fa; padding: 10px; border-radius: 5px; }\\n"

        mw.col.models.add_dict(nt)
