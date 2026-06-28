# Sugestões de nota pelo Editor

## Summary

- What changed: o Editor do Anki ganhou um botão `Sugerir alteração` para notas rastreadas pelo add-on, com seleção dos campos enviados.
- Why: aproximar o fluxo do add-on da camada de interface usada pelo AnkiHub, onde sugestões são iniciadas diretamente no editor da nota.
- User-visible behavior: ao editar uma nota instalada pela plataforma, o usuário pode abrir um diálogo, escolher quais campos entram na sugestão, informar comentário/fonte e enviar para revisão.
- Internal behavior: o botão salva a nota antes de abrir o fluxo, valida login, busca o `card_id` no banco local e envia `POST /addon/cards/{card_id}/suggestions`.

## Implementation

- `gui/editor.py` registra hooks do Editor e habilita o botão somente para notas com metadados locais em `remote_cards`.
- `gui/suggestion_dialog.py` cria o diálogo Qt mínimo com seleção de campos, comentário obrigatório e fonte opcional.
- `services/suggestions.py` extrai os campos da nota, remove campos internos de sync (`Public ID`, `Card ID`, `Version ID`) e filtra campos selecionados.

## Verification

- Automated checks: `python3 -m compileall anki_concursos/gui/editor.py anki_concursos/gui/suggestion_dialog.py anki_concursos/services/suggestions.py anki_concursos/tests/test_suggestions.py`
- Smoke checks: helper puro para seleção de campos.
- Manual Anki checks: not run.

## Risks

- A sugestão envia o estado atual dos campos selecionados. Diff visual, tags e bulk suggestions ficam para blocos posteriores.
