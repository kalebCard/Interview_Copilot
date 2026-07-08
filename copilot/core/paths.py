"""
Single source of truth for all project paths.

This module has ZERO internal imports to avoid circular dependencies.
Every other module that needs paths should import from here.
"""

from pathlib import Path

# Derive project root: paths.py -> core -> copilot -> project_root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = PROJECT_ROOT / "data"
CONTEXT_DIR = DATA_DIR / "context"
SETTINGS_FILE = DATA_DIR / "settings.json"
DB_PATH = DATA_DIR / "interviews.db"
LOG_FILE = DATA_DIR / "copilot.log"
