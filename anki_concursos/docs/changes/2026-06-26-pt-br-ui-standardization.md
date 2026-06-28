# 2026-06-26: Padronização PT-BR da UI

## Summary

- What changed: textos visíveis do add-on foram padronizados para PT-BR.
- Why: reduzir mistura de inglês/português em menus, diálogos e mensagens finais.

## Scope

- Files/modules touched:
  - `anki_concursos/gui/menu.py`
  - `anki_concursos/gui/deck_browser.py`
  - `anki_concursos/gui/status_dialog.py`
  - `anki_concursos/gui/settings_dialog.py`
  - `anki_concursos/sync/engine.py`
  - `anki_concursos/sync/installer.py`
- User-visible behavior: ações, títulos, progresso e resultados agora aparecem em PT-BR.
- Internal behavior: sem mudança de contrato com API, storage ou lógica de sync.

## Before

Menus e mensagens misturavam PT-BR com inglês, por exemplo `Sync Now`, `Browse Decks`,
`Successfully synced`, `Installed` e `Unsubscribe`.

## After

Os mesmos fluxos mostram textos como `Sincronizar agora`, `Explorar baralhos`,
`Sincronizadas N alterações`, `Instalado` e `Cancelar inscrição`.

## Implementation Notes

- Key decisions: traduzir apenas texto exibido ao usuário; logs, nomes internos e contratos da API não foram alterados.
- Anki APIs/hooks touched: nenhum hook novo.
- Backend API contracts touched: nenhum.
- Storage/config changes: nenhuma.

## Verification

- Automated checks:
  - `/tmp/anki-addon-pytest-venv/bin/python -m compileall anki_concursos`
  - `/tmp/anki-addon-pytest-venv/bin/python -m pytest anki_concursos/tests`
- Manual Anki checks: não executado nesta etapa.
- Not run: smoke test real no Anki.

## Risks

- Known risks: textos gerados pelo Qt para botões padrão podem depender da localização do ambiente.
- Rollback notes: reverter este arquivo e as alterações de strings nos módulos listados.

## Follow-ups

- Revisar visualmente no Anki se todos os diálogos cabem bem com textos mais longos em PT-BR.
