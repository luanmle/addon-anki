# 2026-06-27: Detecção de conflito com alterações locais

## Summary

- What changed: sync agora detecta notas locais editadas após o último sync antes de aplicar updates remotos.
- Why: evitar sobrescrita silenciosa de alterações feitas manualmente no Anki.

## Scope

- Files/modules touched:
  - `anki_concursos/services/note_manager.py`
  - `anki_concursos/sync/engine.py`
  - `anki_concursos/tests/test_note_manager.py`
  - `anki_concursos/tests/test_sync.py`
- User-visible behavior: sync aborta com mensagem de conflito local quando um update remoto iria sobrescrever uma nota editada localmente.
- Internal behavior: preflight de conflitos roda antes de qualquer mutação na coleção.

## Before

Se o backend enviasse update para um card que o usuário editou localmente depois do último sync, o add-on podia sobrescrever a nota sem aviso.

## After

Para cards `updated`, o add-on compara `note.mod` com `remote_cards.updated_at`.
Se a nota local foi modificada depois do último sync e o conteúdo remoto mudou, a sincronização é interrompida antes de aplicar alterações.

## Implementation Notes

- Key decisions:
  - Política conservadora: abortar sync em vez de sobrescrever ou avançar watermark.
  - Preflight antes de `mw.progress.start()` e antes de criar backup/aplicar mutations.
  - Updates com `content_hash` igual continuam sem write e sem conflito.
- Anki APIs/hooks touched: leitura de `mw.col.get_note(...).mod`.
- Backend API contracts touched: nenhum.
- Storage/config changes: nenhuma migração.

## Verification

- Automated checks:
  - `/tmp/anki-addon-pytest-venv/bin/python -m compileall anki_concursos`
  - `/tmp/anki-addon-pytest-venv/bin/python -m pytest anki_concursos/tests`
- Manual Anki checks: não executado nesta etapa.
- Not run: smoke test real no Anki.

## Risks

- Known risks: `note.mod` pode marcar mudanças não textuais da nota como conflito; isso é intencional para evitar perda de dados.
- Rollback notes: reverter arquivos listados no escopo.

## Follow-ups

- Adicionar UI dedicada para resolver conflito: preservar local, sobrescrever com remoto, ou duplicar nota.
