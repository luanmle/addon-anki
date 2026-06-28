import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

from aqt import mw
from anki.models import NotetypeDict

logger = logging.getLogger("anki_concursos.services.notetype")

class NoteTypeManager:
    def ensure_note_type(self, manifest) -> None:
        """Ensure note types defined in the manifest exist in Anki."""
        template_groups: Dict[str, Dict[str, Any]] = {}
        if getattr(manifest, "templates", None):
            for template in manifest.templates:
                template_data = self._template_data(template)
                nt_name = template_data.get("note_type")
                if not nt_name:
                    continue
                group = template_groups.setdefault(
                    nt_name,
                    {"fields": [], "templates": []},
                )
                for field_name in template_data.get("fields", []):
                    if field_name and field_name not in group["fields"]:
                        group["fields"].append(field_name)
                group["templates"].append(template_data)

        if template_groups:
            for nt_name, group in template_groups.items():
                existing = mw.col.models.by_name(nt_name)
                field_list = group["fields"]
                templates = group["templates"]
                kind = "cloze" if any(
                    template.get("card_kind") == "cloze"
                    for template in templates
                ) else "basic"
                if existing:
                    self._verify_fields(existing, field_list)
                    self._ensure_templates(existing, templates, kind, field_list)
                    continue
                self._create_note_type(nt_name, kind, field_list, templates)
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

    def _template_data(self, template: Any) -> Dict[str, Any]:
        """Return a dict view over a manifest template.

        `ApiClient.get_deck_manifest()` may return templates as dataclasses,
        while some tests and older call sites still use dicts.
        """
        if isinstance(template, dict):
            return template
        if is_dataclass(template):
            return asdict(template)
        return {
            key: getattr(template, key)
            for key in (
                "template_name",
                "note_type",
                "card_kind",
                "fields",
                "field_mapping",
                "front_html",
                "back_html",
                "styling_css",
            )
            if hasattr(template, key)
        }

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

    def _create_note_type(
        self,
        name: str,
        kind: str,
        fields: List[str],
        templates: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
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
        if templates:
            nt["tmpls"] = []
            self._ensure_templates(nt, templates, kind, fields, save=False)
        elif kind == "basic":
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
            
        if not templates:
            # Add minimal CSS
            nt["css"] += "\\n.answer { color: #28a745; margin-top: 15px; font-weight: bold; }\\n.explanation { margin-top: 15px; font-style: italic; background-color: #f8f9fa; padding: 10px; border-radius: 5px; }\\n"
        
        mw.col.models.add_dict(nt)

    def _ensure_templates(
        self,
        notetype: NotetypeDict,
        templates: List[Dict[str, Any]],
        kind: str,
        fields: List[str],
        save: bool = True,
    ) -> None:
        changed = False
        existing_templates = {
            template.get("name"): template
            for template in notetype.get("tmpls", [])
            if template.get("name")
        }
        managed_template_names: List[str] = []

        for template_data in templates:
            template_name = template_data.get("template_name") or self._default_template_name(kind)
            if template_name not in managed_template_names:
                managed_template_names.append(template_name)
            template = existing_templates.get(template_name)
            if template is None:
                template = mw.col.models.new_template(template_name)
                mw.col.models.add_template(notetype, template)
                existing_templates[template_name] = template
                changed = True

            front_html = template_data.get("front_html") or self._default_front_html(kind, fields)
            back_html = template_data.get("back_html") or self._default_back_html(kind, fields)
            if template.get("qfmt") != front_html:
                template["qfmt"] = front_html
                changed = True
            if template.get("afmt") != back_html:
                template["afmt"] = back_html
                changed = True

        managed_templates = [
            existing_templates[name]
            for name in managed_template_names
            if name in existing_templates
        ]
        if managed_templates and notetype.get("tmpls", []) != managed_templates:
            notetype["tmpls"] = managed_templates
            changed = True

        css = self._template_css(templates)
        if css and notetype.get("css", "") != css:
            notetype["css"] = css
            changed = True

        if save and changed:
            mw.col.models.save(notetype)

    @staticmethod
    def _template_css(templates: List[Dict[str, Any]]) -> str:
        css_parts: List[str] = []
        for template in templates:
            css = template.get("styling_css")
            if isinstance(css, str) and css and css not in css_parts:
                css_parts.append(css)
        return "\n".join(css_parts)

    @staticmethod
    def _default_template_name(kind: str) -> str:
        return "Cloze" if kind == "cloze" else "Card 1"

    @staticmethod
    def _default_front_html(kind: str, fields: List[str]) -> str:
        if kind == "cloze":
            return "{{cloze:%s}}" % (fields[0] if fields else "Text")
        return "{{%s}}" % (fields[0] if fields else "Front")

    @staticmethod
    def _default_back_html(kind: str, fields: List[str]) -> str:
        if kind == "cloze":
            source_field = fields[0] if fields else "Text"
            extra_field = fields[1] if len(fields) > 1 else source_field
            return "{{cloze:%s}}\n\n<br>\n{{%s}}" % (source_field, extra_field)
        back_field = fields[1] if len(fields) > 1 else (fields[0] if fields else "Front")
        return "{{FrontSide}}\n\n<hr id=answer>\n\n{{%s}}" % back_field
