"""Anki version compatibility adapter."""

from anki.utils import version_with_build

def get_anki_version() -> str:
    """Return the current Anki version string."""
    return version_with_build()
