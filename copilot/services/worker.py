
import threading
import queue
import base64
import io
import concurrent.futures
from typing import Callable, Optional, Any
from copilot.core.logger import get_logger
from copilot.core.memory import add_interaction, get_recent_context
from copilot.core.prompts import CLASSIFIER_PROMPT, PROMPTS
from copilot.core.config import build_system_prompt
from copilot.core.llm_client import LLMClient

logger = get_logger(__name__)



class GeminiWorker(threading.Thread):
    def __init__(
        self,
        audio_queue: "queue.Queue[bytes]",
        image_queue: "queue.Queue[object]",
        api_key: str,
        result_callback: Callable[[str], None],
        error_callback: Callable[[str], None],
        context_content: str,
        model_name: str,
        get_code_state_callback: Optional[Callable[[], str]] = None,
        chunk_callback: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(daemon=True, name="GeminiWorkerThread")
        self.audio_queue = audio_queue
        self.image_queue = image_queue
        self.api_key = api_key
        self.result_callback = result_callback
        self.error_callback = error_callback
        self.context_content = context_content
        self.model_name = model_name
        self.get_code_state_callback = get_code_state_callback
        self.chunk_callback = chunk_callback
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        try:
            llm_client = LLMClient(api_key=self.api_key)
            logger.info(f"GeminiWorker iniciado con API key válida — modelo: {self.model_name}")
        except Exception as e:
            self.error_callback(str(e))
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

                recent_context = get_recent_context("default_session", max_tokens=2000)
                if recent_context:
                    memory_text = "\n\nPAST CONVERSATION CONTEXT:\n"
                    for i, turn in enumerate(recent_context):
                        memory_text += f"Turn {i+1}:\n{turn}\n"
                    text_prompt += memory_text

                if self.get_code_state_callback:
                    code_state = self.get_code_state_callback()
                    if code_state and code_state.strip():
                        text_prompt += f"\n\nCURRENT WORKSPACE CODE STATE:\n[CÓDIGO]\n{code_state}\n[/CÓDIGO]\n"

                user_content: list[dict[str, Any]] = [
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
                    
                # 1. Classification Pre-flight (send multimodal content for accurate classification)
                def _classify():
                    try:
                        class_resp = llm_client.generate_chat(
                            model=self.model_name,
                            messages=[
                                {"role": "system", "content": CLASSIFIER_PROMPT},
                                {"role": "user", "content": user_content}
                            ]
                        )
                        cat = class_resp.choices[0].message.content.strip()
                        cat = "".join(c for c in cat if c.isalnum() or c.isspace()).strip()
                        return cat
                    except Exception as e:
                        logger.warning(f"Classification failed: {e}")
                        return "General"

                # Launch classification in a thread to reduce serial latency
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                try:
                    classify_future = executor.submit(_classify)
                
                    # While classification runs, prepare other data
                    category = classify_future.result(timeout=20)
                except concurrent.futures.TimeoutError:
                    logger.warning("Clasificación timeout. Usando categoría por defecto.")
                    category = "General"
                finally:
                    executor.shutdown(wait=True)
                    
                category_prompt = PROMPTS.get(category, PROMPTS["General"])
                dynamic_system_prompt = build_system_prompt(self.context_content, category_prompt)
                
                # 2. Main Generation
                resp = llm_client.generate_chat(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": dynamic_system_prompt
                        },
                        {
                            "role": "user",
                            "content": user_content
                        }
                    ],
                    stream=True
                )
                
                response_text = ""
                for chunk in resp:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            response_text += delta
                            if self.chunk_callback:
                                self.chunk_callback(delta)
                
                if response_text and response_text.strip():
                    if "IGNORE_CHUNK" in response_text:
                        logger.info("Chunk ignorado por no contener pregunta.")
                    else:
                        self.result_callback(response_text)
                        add_interaction("default_session", text_prompt, response_text, category)
                else:
                    logger.info("Gemini devolvió una respuesta vacía para este chunk.")

            except Exception as api_err:
                err_msg = str(api_err).lower()
                if "safety" in err_msg or "block" in err_msg:
                    self.error_callback("Audio ignorado: bloqueado por filtros de seguridad de Gemini.")
                else:
                    self.error_callback(f"Error de la API: {api_err}")

        logger.info("GeminiWorker finalizado.")
