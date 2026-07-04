import json
from pathlib import Path
from typing import Dict, Any
from copilot.core.logger import get_logger

logger = get_logger(__name__)

# To prevent circular import with config.py, compute data path directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SETTINGS_FILE = PROJECT_ROOT / "data" / "settings.json"

DEFAULT_SETTINGS = {
    "VAD_BLOCK_DURATION": 0.25,
    "VAD_SILENCE_TIMEOUT": 1.0,
    "VAD_MAX_DURATION": 10.0,
    "VAD_MAX_DURATION_STT": 2.5,
    "SILENCE_THRESHOLD": 500,
    "SAMPLE_RATE": 16000
}

class SettingsManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance.settings = DEFAULT_SETTINGS.copy()
            cls._instance.load()
        return cls._instance

    def load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings.update(data)
            except Exception as e:
                logger.error(f"Error loading settings: {e}")

    def save(self):
        try:
            SETTINGS_FILE.parent.mkdir(exist_ok=True)
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def set(self, key: str, value: Any):
        self.settings[key] = value
        self.save()

settings_manager = SettingsManager()
