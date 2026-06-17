"""Anki Concursos Add-on."""

try:
    import aqt
    from . import bootstrap
    # Register hooks and initialize the add-on
    bootstrap.setup()
except ImportError:
    # Safely ignore if aqt is not installed (e.g. during unit testing)
    pass

