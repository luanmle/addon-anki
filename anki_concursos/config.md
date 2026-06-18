# Anki Concursos Configuration

- **api_environment**: The target environment preset (`"staging"`, `"production"`, `"local"`, or `"custom"`). Defaults to `"staging"`.
- **api_url**: A custom base URL for the Anki Concursos backend. When `api_environment` is set to `"custom"`, this URL will be used. For presets, leave this empty to use default servers.
- **auto_sync**: If `true`, the add-on will automatically sync your subscribed decks on startup.
- **log_level**: Determines the verbosity of logs (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
- **upload_field_mappings**: Explicit JSON object used by deck upload. Keys are Anki note type names. Values are `{source_field: canonical_field}` mappings. Allowed canonical fields are `front_text`, `back_text`, `answer_text`, and `explanation_text`.

Example:

```json
{
  "Anki Concursos Basic": {
    "Front": "front_text",
    "Back": "back_text",
    "Answer": "answer_text",
    "Explanation": "explanation_text"
  },
  "Getting Started Cloze": {
    "Cloze": "front_text",
    "Extra": "back_text",
    "Deep Dive": "explanation_text"
  }
}
```

