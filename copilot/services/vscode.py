import json
from copilot.core.logger import get_logger
from copilot.core.paths import PROJECT_ROOT

logger = get_logger(__name__)

VSCODE_STATE_FILE = PROJECT_ROOT / "data" / ".vscode_state.json"

# Markers used in the system prompt that must be sanitized in user-provided content
# to prevent prompt injection via code files open in VS Code.
_PROMPT_MARKERS = {
    "[CÓDIGO]":   "[ C Ó D I G O ]",
    "[/CÓDIGO]":  "[ / C Ó D I G O ]",
    "[ESPAÑOL]:": "[ E S P A Ñ O L ]:",
    "[INGLÉS]:":  "[ I N G L É S ]:",
    "IGNORE_CHUNK": "I G N O R E _ C H U N K",
}

def _sanitize_content(text: str) -> str:
    """Neutralize system-prompt markers in user-provided content."""
    for marker, replacement in _PROMPT_MARKERS.items():
        text = text.replace(marker, replacement)
    return text

def read_vscode_state() -> str:
    if not VSCODE_STATE_FILE.exists():
        return ""
    try:
        with open(VSCODE_STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
            file_name = state.get("fileName", "Unknown")
            if not file_name or file_name == "Unknown":
                return ""
                
            selected_text = state.get("selectedText", "")
            full_content = state.get("fullContent", "")
            
            # Truncate content to avoid oversized prompts
            if len(full_content) > 20000:
                full_content = full_content[:20000] + "\n...[TRUNCATED]"
            
            full_content = _sanitize_content(full_content)
            
            result = f"// File: {file_name}\n"
            if selected_text:
                result += f"// [User is currently highlighting this section]:\n{_sanitize_content(selected_text)}\n"
            else:
                result += f"{full_content}\n"
                
            return result
    except Exception as e:
        logger.warning(f"Error reading VS Code state: {e}")
        return ""
