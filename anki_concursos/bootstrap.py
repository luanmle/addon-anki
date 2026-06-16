"""Deferred initialization for the add-on."""

from aqt import mw, gui_hooks

from aqt import mw, gui_hooks

from .utils.logging import setup_logging
from .gui.menu import setup_menu
from .hooks.lifecycle import on_profile_did_open

def setup() -> None:
    """Entry point for the add-on. Defers heavy initialization."""
    gui_hooks.profile_did_open.append(on_profile_open)
    gui_hooks.main_window_did_init.append(on_main_window_init)

def on_profile_open() -> None:
    """Called when an Anki profile is opened."""
    if mw and mw.addonManager:
        try:
            addon_folder = __name__.split('.')[0]
            config = mw.addonManager.getConfig(addon_folder) or {}
            setup_logging(config.get("log_level", "INFO"))
        except Exception:
            pass
            
    # Trigger lifecycle hook
    on_profile_did_open()

def on_main_window_init() -> None:
    """Called when Anki's main window is initialized."""
    setup_menu()
