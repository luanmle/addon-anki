# Installation

## For Users

1. Open Anki.
2. Go to **Tools > Add-ons > Get Add-ons...**
3. Enter the code for the Anki Concursos add-on (TBD).
4. Restart Anki.

## For Developers

1. Clone this repository.
2. Link the `anki_concursos` folder into your Anki add-ons directory:
   - **Windows**: `mklink /D %APPDATA%\Anki2\addons21\anki_concursos C:\path\to\anki_concursos`
   - **macOS**: `ln -s /path/to/anki_concursos ~/Library/Application\ Support/Anki2/addons21/anki_concursos`
   - **Linux**: `ln -s /path/to/anki_concursos ~/.local/share/Anki2/addons21/anki_concursos`
3. Start Anki.

### Running Tests
To run the automated tests locally:
```bash
python -m pytest tests/
```
