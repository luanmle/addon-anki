# 2026-06-26: Versão e histórico de baralho

## Summary

- What changed: telas de baralhos agora mostram versão local, versão remota e status de atualização; `Minhas inscrições` ganhou ação de histórico local.
- Why: aproximar o add-on da navegação por versão/histórico esperada após comparação com AnkiHub.

## Scope

- Files/modules touched:
  - `anki_concursos/gui/deck_browser.py`
  - `anki_concursos/gui/status_dialog.py`
  - `anki_concursos/storage/database.py`
  - `anki_concursos/tests/test_storage.py`
- User-visible behavior:
  - `Explorar baralhos` mostra `Versão local`, `Versão remota` e status como `Atualizado` ou `Atualização disponível`.
  - `Minhas inscrições` mostra as mesmas versões e permite abrir o histórico local de sincronizações do baralho.
- Internal behavior: novo método `DatabaseManager.get_sync_logs(deck_id, limit=10)`.

## Before

As telas mostravam apenas a última release remota ou status instalado/não instalado. O usuário não via claramente se o baralho local estava atrasado nem tinha acesso ao histórico local de sincronização.

## After

O usuário consegue comparar versão local e remota nas tabelas. Para baralhos instalados, o botão `Ver` em `Histórico` exibe os últimos logs locais com releases de origem/destino e contadores de cards adicionados, atualizados, removidos e depreciados.

## Implementation Notes

- Key decisions: usar apenas dados já disponíveis no contrato atual e no SQLite local.
- Anki APIs/hooks touched: nenhum.
- Backend API contracts touched: nenhum contrato atual foi alterado.
- Storage/config changes: nenhuma migração; leitura usa tabela `sync_log` existente.

## Backend Gap

O backend ainda não expõe changelog remoto por release. Para histórico remoto completo, será necessário um endpoint como:

- `GET /addon/decks/{deck_id}/releases`

Resposta sugerida:

- `release_number`
- `published_at`
- `summary` ou `changelog`
- `cards_added`
- `cards_updated`
- `cards_removed`
- `cards_deprecated`

## Verification

- Automated checks:
  - `/tmp/anki-addon-pytest-venv/bin/python -m compileall anki_concursos`
  - `/tmp/anki-addon-pytest-venv/bin/python -m pytest anki_concursos/tests`
- Manual Anki checks: não executado nesta etapa.
- Not run: smoke test real no Anki.

## Risks

- Known risks: o histórico exibido é local; reinstalação/limpeza do banco local remove esse histórico.
- Rollback notes: reverter os arquivos listados no escopo.

## Follow-ups

- Implementar changelog remoto quando o backend expuser releases por baralho.
