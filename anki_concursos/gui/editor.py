import functools
import json
from typing import List, Tuple

from aqt import gui_hooks, mw
from aqt.editor import Editor
from aqt.utils import tooltip

from ..api.client import ApiClient
from ..services.suggestions import note_fields_for_suggestion
from ..storage.database import DatabaseManager
from .login_dialog import LoginDialog
from .suggestion_dialog import SuggestionDialog


SUGGESTION_BUTTON_ID = "anki-concursos-suggestion"


def setup_editor() -> None:
    gui_hooks.editor_did_init_buttons.append(_setup_editor_buttons)
    gui_hooks.editor_did_load_note.append(_refresh_button)
    gui_hooks.editor_did_init.append(_refresh_button)


def _setup_editor_buttons(buttons: List[str], editor: Editor) -> None:
    button = editor.addButton(
        icon=None,
        cmd=SUGGESTION_BUTTON_ID,
        func=lambda editor: editor.call_after_note_saved(
            functools.partial(_on_suggestion_button_press, editor),
            keepFocus=True,
        ),
        tip="Sugerir alteração para a plataforma",
        label="Sugerir alteração",
        id=SUGGESTION_BUTTON_ID,
        disables=False,
    )
    buttons.append(button)
    buttons.append(
        "<style>"
        f"#{SUGGESTION_BUTTON_ID}[disabled] {{ opacity: .45; }}"
        "</style>"
    )


def _on_suggestion_button_press(editor: Editor) -> None:
    note = editor.note
    if note is None or note.id == 0:
        return

    api, db = _services()
    if not api.auth_service.get_token():
        LoginDialog(api, mw).exec()
        if not api.auth_service.get_token():
            tooltip("Faça login para enviar sugestões.", parent=editor.widget)
            return

    card = db.get_card_by_anki_note_id(int(note.id))
    if card is None:
        tooltip("Esta nota não está vinculada a um card da plataforma.", parent=editor.widget)
        return

    fields = note_fields_for_suggestion(note)
    if not fields:
        tooltip("Nenhum campo editável encontrado para sugerir.", parent=editor.widget)
        return

    SuggestionDialog(
        api=api,
        card_id=card.card_id,
        fields=fields,
        original_fields=card.remote_fields,
        parent=editor.widget,
    ).exec()


def _refresh_button(editor: Editor) -> None:
    if editor is None or editor.web is None:
        return

    enabled = False
    note = editor.note
    if note is not None and note.id:
        try:
            _, db = _services()
            enabled = db.get_card_by_anki_note_id(int(note.id)) is not None
        except Exception:
            enabled = False

    editor.web.eval(
        f"""
        (() => {{
            const button = document.getElementById({json.dumps(SUGGESTION_BUTTON_ID)});
            if (button) button.disabled = {str(not enabled).lower()};
        }})();
        """
    )


def _services() -> Tuple[ApiClient, DatabaseManager]:
    if not hasattr(mw, "anki_concursos_api"):
        mw.anki_concursos_api = ApiClient()
    if not hasattr(mw, "anki_concursos_db"):
        mw.anki_concursos_db = DatabaseManager()
    return mw.anki_concursos_api, mw.anki_concursos_db
