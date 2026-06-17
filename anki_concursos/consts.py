"""Constants used throughout the add-on."""

ADDON_NAME = "Anki Concursos"
VERSION = "0.1.0"

# Note types
NOTE_TYPE_BASIC = "Anki Concursos Basic"
NOTE_TYPE_CLOZE = "Anki Concursos Cloze"

# Logging
LOG_FILE = "anki_concursos.log"

# Add-on configuration defaults
DEFAULT_API_ENVIRONMENT = "staging"

API_ENVIRONMENTS = {
    "local": "http://localhost:8000",
    "staging": "https://flashcards-stagging-d9c092f5d04d.herokuapp.com",
    "production": "https://api.seudominio.com",
}

DEFAULT_API_URL = API_ENVIRONMENTS[DEFAULT_API_ENVIRONMENT]

