# Anki add-on architecture references

Anki loads add-ons as Python modules at startup. The UI uses Python/PyQt and selected screens use web technologies. Keep startup registration small and defer collection-dependent work until the relevant lifecycle state.

## Official sources

- [Introduction](https://addon-docs.ankiweb.net/)
- [Official Anki source](https://github.com/ankitects/anki)
- [Official demo add-ons](https://github.com/ankitects/anki-addons/tree/master/demos)
