
import threading
import queue
import base64
import io
from typing import Callable
from copilot.config import GEMINI_MODEL
from copilot.logger import get_logger

logger = get_logger(__name__)

class GeminiWorker(threading.Thread):
    def __init__(
        self,
        audio_queue: "queue.Queue[bytes]",
        image_queue: "queue.Queue[object]",
        api_key: str,
        result_callback: Callable[[str], None],
        error_callback: Callable[[str], None],
        system_prompt: str,
        get_code_state_callback: Callable[[], str] = None,
    ):
        super().__init__(daemon=True, name="GeminiWorkerThread")
        self.audio_queue     = audio_queue
        self.image_queue     = image_queue
        self.api_key         = api_key
        self.result_callback = result_callback
        self.error_callback  = error_callback
        self.system_prompt   = system_prompt
        self.get_code_state_callback = get_code_state_callback
        self.memory_buffer   = []
        self._stop_event     = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        try:
            import openai
        except ImportError:
            self.error_callback("openai no instalado. Ejecuta: pip install openai")
            return
        client_or = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key)
            
        if self.api_key:
            logger.info(f"GeminiWorker iniciado con API key válida — modelo: {GEMINI_MODEL}")
        else:
            self.error_callback("API key inválida")
            return

        while not self._stop_event.is_set():
            wav_bytes = None
            img_bytes = None

            try:
                wav_bytes = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                pass

            try:
                img_obj = self.image_queue.get_nowait()
                if img_obj and hasattr(img_obj, 'convert'):
                    buf = io.BytesIO()
                    img_obj.convert("RGB").save(buf, format="JPEG")
                    img_bytes = buf.getvalue()
            except (queue.Empty, AttributeError, Exception) as e:
                if not isinstance(e, queue.Empty):
                    logger.warning(f"Error procesando imagen: {e}")
                pass

            if wav_bytes is None and img_bytes is None:
                continue

            try:
                text_prompt = (
                    "Analyze the interview question spoken in this audio clip "
                    "(and the provided screenshot if present) "
                    "and provide your structured [ESPAÑOL] / [INGLÉS] response "
                    "according to your instructions."
                )

                if self.memory_buffer:
                    memory_text = "\n\nPAST CONVERSATION CONTEXT (last few turns):\n"
                    for i, turn in enumerate(self.memory_buffer):
                        memory_text += f"Turn {i+1}: {turn}\n"
                    text_prompt += memory_text

                if self.get_code_state_callback:
                    current_code = self.get_code_state_callback()
                    if current_code:
                        text_prompt += f"\n\nCURRENT WORKSPACE CODE STATE:\n```\n{current_code}\n```"                
                response_text = ""

                user_content = [
                    {"type": "text", "text": text_prompt}
                ]
                
                if wav_bytes:
                    base64_audio = base64.b64encode(wav_bytes).decode("utf-8")
                    user_content.append({
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64_audio,
                            "format": "wav"
                        }
                    })
                if img_bytes:
                    base64_img = base64.b64encode(img_bytes).decode("utf-8")
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                    })
                    
                resp = client_or.chat.completions.create(
                    model=GEMINI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": self.system_prompt
                        },
                        {
                            "role": "user",
                            "content": user_content
                        }
                    ]
                )
                response_text = resp.choices[0].message.content or ""

                if response_text and response_text.strip():
                    if "IGNORE_CHUNK" in response_text:
                        logger.info("Chunk ignorado por no contener pregunta.")
                    else:
                        self.result_callback(response_text)
                        
                        # Guardar en la memoria a corto plazo si hubo respuesta válida
                        self.memory_buffer.append(response_text)
                        
                        estimated_tokens = sum(len(text.split()) * 1.3 for text in self.memory_buffer)
                        while estimated_tokens > 2000 and len(self.memory_buffer) > 1:
                            self.memory_buffer.pop(0)
                            estimated_tokens = sum(len(text.split()) * 1.3 for text in self.memory_buffer)
                else:
                    logger.info("Gemini devolvió una respuesta vacía para este chunk.")

            except Exception as api_err:
                err_msg = str(api_err).lower()
                if "safety" in err_msg or "block" in err_msg:
                    self.error_callback("Audio ignorado: bloqueado por filtros de seguridad de Gemini.")
                elif "429" in err_msg or "quota" in err_msg or "too many requests" in err_msg:
                    self.error_callback("Límite de API alcanzado (429). Pausando 10 segundos...")
                    import time
                    time.sleep(10)
                else:
                    self.error_callback(f"Error de la API: {api_err}")

        logger.info("GeminiWorker finalizado.")
