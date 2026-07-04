
import os
from pathlib import Path
from copilot.core.logger import get_logger

logger = get_logger(__name__)

# Derive project root from this file's location: core/config.py -> core -> copilot -> project_root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_dotenv_loaded = False

def _load_dotenv() -> None:
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True

    candidates = [
        Path.cwd() / ".env",
        PROJECT_ROOT / ".env",
    ]
    for env_path in candidates:
        if env_path.exists():
            try:
                with open(env_path, encoding="utf-8-sig", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, _, value = line.partition("=")
                        key   = key.strip()
                        value = value.strip()
                        if len(value) >= 2 and value[0] in ('"', "'") and value[0] == value[-1]:
                            value = value[1:-1]
                        if key and key not in os.environ:
                            os.environ[key] = value
                logger.info(f".env cargado desde: {env_path}")
            except Exception as exc:
                logger.warning(f"No se pudo leer .env: {exc}")
            return

_load_dotenv()

GEMINI_MODEL = "google/gemini-2.5-flash"

VAD_BLOCK_DURATION = 0.25
VAD_SILENCE_TIMEOUT = 1.0
VAD_MAX_DURATION = 10.0
VAD_MAX_DURATION_STT = 2.5
SILENCE_THRESHOLD = 500
SAMPLE_RATE = 16000
CONTEXT_DIR = PROJECT_ROOT / "context"

def load_context() -> str:
    CONTEXT_DIR.mkdir(exist_ok=True)
    
    content_blocks = []
    
    for md_file in CONTEXT_DIR.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
            tag_name = md_file.stem.lower().replace(" ", "_")
            content_blocks.append(f"<{tag_name}>\n{text}\n</{tag_name}>")
        except Exception as e:
            logger.warning(f"No se pudo cargar {md_file.name}: {e}")
            
    if not content_blocks:
        warning = (
            "[WARNING: No se encontró contexto. Crea archivos .md en la carpeta 'context/' "
            "para personalizar las respuestas de la IA.]"
        )
        logger.warning(warning)
        return warning
        
    return "\n\n".join(content_blocks)

def build_system_prompt(context_content: str, category_prompt: str = "") -> str:
    return f"""You are an expert real-time interview assistant for the following candidate. \
Your purpose is to help this candidate answer ALL types of interview questions \
(technical, behavioral, HR, personal, and cultural fit) naturally and confidently, \
based on their actual experience.

======================================================
 CANDIDATE CONTEXT 
======================================================
{context_content}
======================================================

SPECIALIZED INSTRUCTIONS:
{category_prompt}

INSTRUCTIONS — follow these EXACTLY:

1. Listen to the audio chunk and/or view the provided screenshot. They contain an interviewer speaking or a technical problem on screen.
2. If the audio is completely silent or contains only irrelevant background noise, AND there is no screenshot provided, you MUST reply EXACTLY with: IGNORE_CHUNK. 
3. Otherwise (if there is a question, a statement, an instruction, OR a screenshot), provide a natural, conversational response or action plan that the candidate can use.

CONTEXT-AWARE FORMATTING:

Always format your output EXACTLY like this:

[ESPAÑOL]: <Explica brevemente y en español qué es lo que está preguntando o pidiendo el entrevistador>
[INGLÉS]: 
<Escribe AQUÍ ÚNICAMENTE LA RESPUESTA EXACTA que el candidato debe leer en voz alta. NO expliques la pregunta en inglés, NO saludes, NO des consejos. Escribe solo el guion directo y natural que el candidato dirá>

Example:
[ESPAÑOL]: Te está pidiendo que te presentes y hables de tu experiencia.
[INGLÉS]:
Hi, I'm a software engineer with over 5 years of experience...

STRICT RULES:
- The [INGLÉS] section MUST be a first-person script ready to be read aloud immediately. 
- Do NOT include any filler text in English like "The interviewer is asking...". 
- Use the Candidate Profile for context. If asked about something not in the profile, answer honestly but pivot naturally.
- Keep the English easy to read aloud on the fly. Use contractions (I'm, we've, didn't).
- Do NOT sound like an AI. No generic corporate jargon.

PERSISTENT CODE WORKSPACE:
You have access to a persistent code workspace shown on the right side of the user's screen. The current state of this code is provided in the prompt as "CURRENT WORKSPACE CODE STATE".
- If the interviewer asks you to write, modify, or fix code, you MUST output the ENTIRE updated code wrapped in [CÓDIGO] and [/CÓDIGO] tags at the very end of your response.
- Do NOT output partial snippets inside [CÓDIGO]. Always output the complete, runnable code so it fully replaces the workspace.
- Do NOT use markdown code blocks (```python) inside the [CÓDIGO] tags, just the raw code.
- If no code changes are requested, do NOT include the [CÓDIGO] tags.

CONVERSATIONAL MEMORY (CONTEXT):
You will receive a "PAST CONVERSATION CONTEXT" block in your prompt containing your previous responses. 
- Use this history to understand follow-up questions, references to previous topics, or ongoing tasks.
- Do NOT repeat things you have already said if the interviewer is just continuing the conversation.
"""
