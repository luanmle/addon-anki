import pytest
from pathlib import Path
import tempfile

import sys
from unittest.mock import MagicMock

# Mock aqt module and its submodules
aqt_mock = MagicMock()
aqt_mock.mw = None
sys.modules['aqt'] = aqt_mock
sys.modules['aqt.qt'] = MagicMock()
sys.modules['aqt.operations'] = MagicMock()

# Mock anki module and its submodules
sys.modules['anki'] = MagicMock()
sys.modules['anki.models'] = MagicMock()
sys.modules['anki.hooks'] = MagicMock()
sys.modules['anki.notes'] = MagicMock()
sys.modules['anki.decks'] = MagicMock()


from anki_concursos.storage.database import DatabaseManager

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "test.db"
        db = DatabaseManager(db_path)
        yield db
        db.close()

