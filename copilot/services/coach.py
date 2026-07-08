from copilot.core.memory import get_session_history
from copilot.core.logger import get_logger
from copilot.core.llm_client import LLMClient
from copilot.core.settings import settings_manager

logger = get_logger(__name__)

# Maximum interactions to include in a coach report to avoid exceeding model context limits.
_MAX_COACH_INTERACTIONS = 50

def generate_coach_report(session_id: str = "default_session") -> str:
    history = get_session_history(session_id)
    if not history:
        return "No hay suficientes datos en la sesión para generar un reporte."
    
    # Truncate to last N interactions to stay within context window
    if len(history) > _MAX_COACH_INTERACTIONS:
        history = history[-_MAX_COACH_INTERACTIONS:]
    
    transcript = ""
    for ts, cat, q, a in history:
        transcript += f"Categoría: {cat}\nQ: {q}\nA: {a}\n\n"
        
    prompt = f"""Eres un Coach de Entrevistas Técnicas. Evalúa el siguiente desempeño de un candidato en base a la transcripción. 
Proporciona calificaciones (0 a 10) para: 
1. Claridad de respuesta
2. Uso de ejemplos (STAR method)
3. Precisión técnica

Luego, da 3 puntos fuertes y 3 áreas de mejora detalladas. Mantén un tono alentador pero crítico.

TRANSCRIPCIÓN:
{transcript}
"""
    
    try:
        model = settings_manager.get("model", "google/gemini-2.5-flash")
        client = LLMClient()
        resp = client.generate_chat(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generando reporte de coach: {e}")
        return "Error al generar el reporte del Coach."

