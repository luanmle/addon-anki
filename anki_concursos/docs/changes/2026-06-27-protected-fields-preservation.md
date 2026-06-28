# Preservação de campos protegidos no sync

- Date: 2026-06-27
- Area: add-on sync / Anki collection data
- Type: implementation

## Summary

O sync agora aceita `protected_fields` no contrato remoto e preserva esses campos ao atualizar uma nota existente.

## Why

Na comparação com AnkiHub, campos protegidos são um bloco importante para evitar perda de personalizações locais. Sem isso, um update remoto poderia sobrescrever campos que o usuário mantém localmente.

## Behavior

Antes:

- Todo campo recebido pelo backend podia ser aplicado sobre a nota local.
- O add-on não aceitava `protected_fields` em manifesto, template ou mudança de sync.

Depois:

- `protected_fields` pode vir de:
  - `change.protected_fields`;
  - `change.template.protected_fields`;
  - `manifest.templates[].protected_fields`;
  - `manifest.supported_note_types[kind].protected_fields`;
  - `manifest.protected_fields`.
- Em updates de nota existente, campos protegidos não são sobrescritos.
- Em nota nova, todos os campos continuam sendo preenchidos normalmente.
- Em fluxo legado com `field_mapping`, nomes canônicos como `front_text` também são convertidos para o campo real do Anki, como `Front`.

## Implementation Notes

- `sync/fields.py` ganhou `protected_fields_for_change()`.
- `NoteManager.update_note()` ganhou parâmetro opcional `protected_fields`.
- `SyncEngine` e `DeckInstaller` passam `protected_fields` somente quando o contrato informa algum campo protegido.
- Dataclasses da API aceitam `protected_fields` sem quebrar backends antigos.
- `NoteManager.note_exists()` foi corrigido para voltar a consultar `mw.col.get_note()`.

## Verification

Commands:

```bash
/tmp/anki-addon-pytest-venv/bin/python -m compileall anki_concursos
/tmp/anki-addon-pytest-venv/bin/python -m pytest anki_concursos/tests
```

Result:

- `compileall` passed.
- `89 passed`.

## Manual Test Needed

Ainda falta smoke test real no Anki com backend ou mock local enviando `protected_fields`, editando localmente um campo protegido e confirmando que o update remoto não altera esse campo.
