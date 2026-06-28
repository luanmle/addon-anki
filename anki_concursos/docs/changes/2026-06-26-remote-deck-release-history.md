# 2026-06-26: Histórico remoto de releases

## Summary

- What changed: `Minhas inscrições` agora busca histórico remoto de releases no backend.
- Why: completar o bloco de histórico/versão de baralho ponta a ponta.

## Scope

- Files/modules touched:
  - `anki_concursos/api/models.py`
  - `anki_concursos/api/client.py`
  - `anki_concursos/gui/status_dialog.py`
  - `anki_concursos/tests/test_client.py`
  - `anki_concursos/tests/test_status_dialog.py`
- User-visible behavior: botão `Histórico > Ver` tenta exibir releases remotas com resumo e contadores por ação.
- Internal behavior: novo `ApiClient.get_deck_releases(deck_id, page=1, page_size=20)`.

## Before

O histórico do add-on era apenas local, baseado em `sync_log`.

## After

O add-on consulta `GET /addon/decks/{deck_id}/releases`. Quando o endpoint remoto falha ou não existe, a UI cai para o histórico local já existente.

## Implementation Notes

- Key decisions: manter fallback local para compatibilidade com backends antigos.
- Anki APIs/hooks touched: nenhum.
- Backend API contracts touched: usa `GET /addon/decks/{deck_id}/releases`.
- Storage/config changes: nenhuma.

## Verification

- Automated checks:
  - `/tmp/anki-addon-pytest-venv/bin/python -m compileall anki_concursos`
  - `/tmp/anki-addon-pytest-venv/bin/python -m pytest anki_concursos/tests`
- Manual Anki checks: não executado nesta etapa.
- Not run: smoke test real no Anki.

## Risks

- Known risks: diálogo usa texto simples; releases longas podem gerar mensagem extensa.
- Rollback notes: reverter arquivos listados no escopo.

## Follow-ups

- Trocar mensagem simples por diálogo/tabela dedicada se o histórico remoto crescer.
