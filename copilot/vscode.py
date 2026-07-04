import json
from pathlib import Path
from copilot.logger import get_logger

logger = get_logger(__name__)

VSCODE_STATE_FILE = Path.cwd() / ".vscode_state.json"

def read_vscode_state() -> str:
    if not VSCODE_STATE_FILE.exists():
        return ""
    try:
        with open(VSCODE_STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
            file_name = state.get("fileName", "Unknown")
            selected_text = state.get("selectedText", "")
            full_content = state.get("fullContent", "")
            
            result = f"// File: {file_name}\n"
            if selected_text:
                result += f"// [User is currently highlighting this section]:\n{selected_text}\n"
            else:
                result += f"{full_content}\n"
                
            return result
    except Exception as e:
        logger.warning(f"Error reading VS Code state: {e}")
        return ""
