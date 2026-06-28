# 2026-06-27: Preview antes/depois em sugestões

## Summary

- What changed: o diálogo de sugestão agora mostra prévia `Antes/Depois` dos campos selecionados.
- Why: aproximar o fluxo do AnkiHub, onde o usuário revisa o conteúdo enviado antes de submeter.

## Scope

- Files/modules touched: `gui/suggestion_dialog.py`, `gui/editor.py`, `services/suggestions.py`, `storage/database.py`, `storage/models.py`, `sync/fields.py`, `sync/engine.py`, `sync/installer.py`.
- User-visible behavior: ao abrir `Sugerir alteração`, o usuário vê quais campos serão enviados e o valor remoto anterior quando disponível.
- Internal behavior: o add-on salva `remote_fields` em `remote_cards` como JSON do último conteúdo remoto aplicado.

## Before

O diálogo permitia escolher campos, mas não mostrava o conteúdo remoto anterior. O usuário via apenas nomes dos campos.

## After

Cada card rastreado pode carregar um snapshot local dos campos remotos. O diálogo compara esse snapshot com os campos atuais da nota e mostra uma prévia textual compacta.

## Implementation Notes

- Key decisions: guardar snapshot local evita chamada remota no clique do editor.
- Anki APIs/hooks touched: sem novo hook; usa o botão de editor já registrado.
- Backend API contracts touched: nenhum endpoint novo.
- Storage/config changes: `remote_cards.remote_fields TEXT` adicionado via migração leve em `_init_db()`.

## Verification

- Automated checks: `python3 -m compileall anki_concursos/gui/editor.py anki_concursos/gui/suggestion_dialog.py anki_concursos/services/suggestions.py anki_concursos/storage/database.py anki_concursos/storage/models.py anki_concursos/sync/fields.py anki_concursos/sync/engine.py anki_concursos/sync/installer.py anki_concursos/tests/test_suggestions.py anki_concursos/tests/test_contract.py anki_concursos/tests/test_storage.py`
- Manual Anki checks: not run.
- Not run: `pytest`, unavailable in current Python environment.

## Risks

- Known risks: cards instalados antes deste bloco só terão `remote_fields` após novo sync/install que passe pelo card.
- Rollback notes: remover coluna não é necessário para rollback funcional; código antigo ignoraria coluna extra.

## Follow-ups

- Backfill opcional de `remote_fields` para cards já instalados, se a ausência de preview em cards antigos incomodar.
