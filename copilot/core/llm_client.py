import os
import time
from typing import List, Dict, Any, Optional
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

from copilot.core.logger import get_logger

logger = get_logger(__name__)

class LLMClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://openrouter.ai/api/v1"):
        if OpenAI is None:
            raise ImportError("openai no instalado. Ejecuta: pip install openai")
        
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not self.api_key:
            raise ValueError("API key de OpenRouter no configurada o vacía")
        
        self.client = OpenAI(base_url=base_url, api_key=self.api_key)

    def generate_chat(self, model: str, messages: List[Dict[str, Any]], stream: bool = False, max_retries: int = 3):
        attempt = 0
        while attempt < max_retries:
            try:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore
                    stream=stream
                )
                return resp
            except Exception as api_err:
                err_msg = str(api_err).lower()
                if "429" in err_msg or "quota" in err_msg or "too many requests" in err_msg:
                    attempt += 1
                    logger.warning(f"Límite de API alcanzado (429). Reintentando en 5s... (Intento {attempt}/{max_retries})")
                    if attempt >= max_retries:
                        raise api_err
                    time.sleep(5)
                else:
                    raise api_err
        raise Exception("Se alcanzó el número máximo de reintentos.")
