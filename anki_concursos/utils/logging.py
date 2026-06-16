import logging
import sys
from pathlib import Path
from typing import Optional

from aqt import mw

from ..consts import LOG_FILE

logger = logging.getLogger("anki_concursos")
_setup_done = False


def setup_logging(log_level: str = "INFO") -> None:
    """Initialize logging for the add-on."""
    global _setup_done
    if _setup_done:
        return

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Set up file handler
    if mw and mw.addonManager:
        # Find the actual add-on directory name (might not be exactly anki_concursos)
        # However, for anki >= 2.1, it's easier to use the current module path
        try:
            # Create user_files inside the addon folder
            addon_dir = Path(__file__).parent.parent
            user_files = addon_dir / "user_files"
            user_files.mkdir(exist_ok=True)
            
            log_path = user_files / LOG_FILE
            
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Fallback if we can't write to file
            print(f"Anki Concursos: Failed to setup file logging: {e}", file=sys.stderr)

    # Set up console handler (for Anki console/stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _setup_done = True
