import json
from typing import Dict, Any, List, Tuple
from copilot.core.logger import get_logger
from copilot.core.paths import SETTINGS_FILE

logger = get_logger(__name__)

MODELS: List[Tuple[str, str]] = [
    ("Rapidez Extrema - Gemini 2.5 Flash",   "google/gemini-2.5-flash"),
    ("Agil - Gemini 2.5 Pro",                "google/gemini-2.5-pro"),
    ("Inteligente - Claude Sonnet 4.6",       "anthropic/claude-sonnet-4-6"),
    ("Maxima Inteligencia - Claude Opus 4.8", "anthropic/claude-opus-4-8"),
]

DEFAULTS: Dict[str, Any] = {
    "hotkey_toggle_visibility": "ctrl+shift+h",
    "hotkey_capture_screen":    "ctrl+shift+s",
    "hotkey_toggle_ai":         "ctrl+shift+a",
    "hotkey_toggle_stt":        "ctrl+shift+t",
    "model":                    "google/gemini-2.5-flash",
    "silence_threshold":        500,
    "vad_max_duration":         10.0,
    "vad_silence_timeout":      1.0,
    "vad_block_duration":       0.25,
    "vad_max_duration_stt":     2.5,
    "sample_rate":              16000,
}

class SettingsManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance.settings = DEFAULTS.copy()
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
        return self.settings.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any):
        self.settings[key] = value
        self.save()

settings_manager = SettingsManager()

def load_settings() -> Dict[str, Any]:
    settings_manager.load()
    return settings_manager.settings

def save_settings(data: Dict[str, Any]) -> None:
    settings_manager.settings.update(data)
    settings_manager.save()

