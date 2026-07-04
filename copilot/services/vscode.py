import json
from pathlib import Path
from copilot.core.logger import get_logger
from copilot.core.config import PROJECT_ROOT

logger = get_logger(__name__)

VSCODE_STATE_FILE = PROJECT_ROOT / "data" / ".vscode_state.json"

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
            
            # Basic prompt injection protection
            full_content = full_content.replace("[/CÓDIGO]", "[ C Ó D I G O ]")
            full_content = full_content.replace("[INGLÉS]", "[ I N G L É S ]")
            
            result = f"// File: {file_name}\n"
            if selected_text:
                result += f"// [User is currently highlighting this section]:\n{selected_text}\n"
            else:
                result += f"{full_content}\n"
                
            return result
    except Exception as e:
        logger.warning(f"Error reading VS Code state: {e}")
        return ""
