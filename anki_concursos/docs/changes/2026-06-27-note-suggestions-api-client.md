# 2026-06-27: Cliente de API para sugestoes de nota

## Resumo

O cliente HTTP do add-on agora consegue enviar sugestoes de nota e nota nova
para o backend da plataforma.

## O que mudou

- `anki_concursos/api/models.py`
  - novos dataclasses `NoteSuggestionRequest` e `NoteSuggestionResponse`.
- `anki_concursos/api/client.py`
  - novos metodos:
    - `create_card_suggestion(card_id, payload)`
    - `create_new_note_suggestion(deck_id, payload)`
- `anki_concursos/tests/test_client.py`
  - cobertura dos dois endpoints novos.

## Contrato

- `POST /addon/cards/{card_id}/suggestions`
- `POST /addon/decks/{deck_id}/note-suggestions`

## Observacao

Ainda nao ha tela no add-on atual para disparar esses metodos. Este passo deixa
o contrato pronto para a etapa de UI sem antecipar fluxo desnecessario.
