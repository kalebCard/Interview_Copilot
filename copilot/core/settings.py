import json
from typing import Any, Dict, List, Tuple
from copilot.core.config import PROJECT_ROOT
from copilot.core.logger import get_logger

logger = get_logger(__name__)

SETTINGS_FILE = PROJECT_ROOT / "data" / "settings.json"

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
}

_settings: Dict[str, Any] = {}


def load_settings() -> Dict[str, Any]:
    global _settings
    _settings = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            _settings.update({k: v for k, v in data.items() if k in DEFAULTS})
        except Exception as e:
            logger.warning(f"No se pudo leer settings.json: {e}")
    return _settings


def save_settings(data: Dict[str, Any]) -> None:
    global _settings
    _settings.update(data)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(_settings, f, indent=2, ensure_ascii=False)
        logger.info("settings.json guardado.")
    except Exception as e:
        logger.error(f"No se pudo guardar settings.json: {e}")


def get(key: str, default: Any = None) -> Any:
    if not _settings:
        load_settings()
    return _settings.get(key, DEFAULTS.get(key, default))
