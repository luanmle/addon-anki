import pytest
from pathlib import Path
import tempfile

from anki_concursos.storage.database import DatabaseManager

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "test.db"
        db = DatabaseManager(db_path)
        yield db
