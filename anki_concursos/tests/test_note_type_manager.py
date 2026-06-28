from dataclasses import dataclass
from unittest.mock import patch

from anki_concursos.api.models import AnkiDeckTemplateResponse
from anki_concursos.services.note_type_manager import NoteTypeManager


@dataclass
class Manifest:
    templates: list
    supported_note_types: dict


class FakeModels:
    def __init__(self):
        self.notetypes = {
            "Basic": {"name": "Basic", "flds": [], "tmpls": [], "css": ""},
            "Cloze": {"name": "Cloze", "type": 1, "flds": [], "tmpls": [], "css": ""},
        }
        self.added = None
        self.saved = []

    def by_name(self, name):
        return self.notetypes.get(name)

    def new(self, name):
        return {"name": name, "flds": [], "tmpls": [], "css": ""}

    def copy(self, notetype):
        return {
            "name": notetype["name"],
            "type": notetype.get("type", 0),
            "flds": list(notetype.get("flds", [])),
            "tmpls": [dict(template) for template in notetype.get("tmpls", [])],
            "css": notetype.get("css", ""),
        }

    def new_field(self, name):
        return {"name": name}

    def add_field(self, notetype, field):
        notetype["flds"].append(field)

    def new_template(self, name):
        return {"name": name, "qfmt": "", "afmt": ""}

    def add_template(self, notetype, template):
        notetype["tmpls"].append(template)

    def add_dict(self, notetype):
        self.added = notetype
        self.notetypes[notetype["name"]] = notetype

    def save(self, notetype):
        self.saved.append(notetype)


def test_ensure_note_type_creates_native_templates_from_dataclass_manifest():
    manifest = Manifest(
        templates=[
            AnkiDeckTemplateResponse(
                template_name="Card 1",
                note_type="Meu Modelo Customizado",
                card_kind="basic",
                fields=["Enunciado", "Alternativas", "Comentario"],
                field_mapping={"Enunciado": "front_text"},
                front_html="<section>{{Enunciado}}</section>",
                back_html="<section>{{Alternativas}}{{Comentario}}</section>",
                styling_css=".card { font-family: Arial; }",
            )
        ],
        supported_note_types={},
    )
    fake_models = FakeModels()

    with patch("anki_concursos.services.note_type_manager.mw") as mock_mw:
        mock_mw.col.models = fake_models

        NoteTypeManager().ensure_note_type(manifest)

    created = fake_models.added
    assert created["name"] == "Meu Modelo Customizado"
    assert [field["name"] for field in created["flds"]] == [
        "Public ID",
        "Card ID",
        "Version ID",
        "Enunciado",
        "Alternativas",
        "Comentario",
    ]
    assert created["tmpls"] == [
        {
            "name": "Card 1",
            "qfmt": "<section>{{Enunciado}}</section>",
            "afmt": "<section>{{Alternativas}}{{Comentario}}</section>",
        }
    ]
    assert created["css"] == ".card { font-family: Arial; }"


def test_ensure_note_type_updates_existing_template_html_and_fields():
    existing = {
        "name": "Meu Modelo Customizado",
        "flds": [{"name": "Public ID"}],
        "tmpls": [
            {"name": "Modelo antigo", "qfmt": "{{Front}}", "afmt": "{{Back}}"},
            {"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{Back}}"},
        ],
        "css": "",
    }
    fake_models = FakeModels()
    fake_models.notetypes["Meu Modelo Customizado"] = existing
    manifest = Manifest(
        templates=[
            {
                "template_name": "Card 1",
                "note_type": "Meu Modelo Customizado",
                "card_kind": "basic",
                "fields": ["Enunciado", "Comentario"],
                "field_mapping": {},
                "front_html": "{{Enunciado}}",
                "back_html": "{{FrontSide}}\n\n{{Comentario}}",
                "styling_css": ".card { color: #111; }",
            }
        ],
        supported_note_types={},
    )

    with patch("anki_concursos.services.note_type_manager.mw") as mock_mw:
        mock_mw.col.models = fake_models

        NoteTypeManager().ensure_note_type(manifest)

    assert [field["name"] for field in existing["flds"]] == [
        "Public ID",
        "Card ID",
        "Version ID",
        "Enunciado",
        "Comentario",
    ]
    assert [template["name"] for template in existing["tmpls"]] == ["Card 1"]
    assert existing["tmpls"][0]["qfmt"] == "{{Enunciado}}"
    assert existing["tmpls"][0]["afmt"] == "{{FrontSide}}\n\n{{Comentario}}"
    assert existing["css"] == ".card { color: #111; }"
    assert fake_models.saved
