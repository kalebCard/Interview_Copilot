
import threading
import queue
import io
import re
import concurrent.futures
import speech_recognition as sr
from copilot.core.logger import get_logger

logger = get_logger(__name__)

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None
    logger.error("deep-translator no instalado. Ejecuta: pip install deep-translator")
from typing import Callable, Optional

MAX_CONCURRENT_PROCESSING = 3



def normalize_text(text: str) -> str:

    if not text:
        return ""
    text = text.strip()
    return re.sub(r"\s{2,}", " ", text)

def is_valid_text(text: str) -> bool:

    if not text:
        return False
    text_stripped = text.strip()
    if len(text_stripped) < 2:
        return False
    if len(text_stripped.split()) < 1:
        return False
    if text_stripped.lower() in ["eh", "uh", "um", "ah", "hmm", "mmm"]:
        return False
    return True

class TranscriptionWorker(threading.Thread):
    def __init__(
        self,
        stt_queue: "queue.Queue[bytes]",
        subtitle_callback: Callable[[str], None],
        error_callback: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(daemon=True, name="TranscriptionThread")
        self.stt_queue = stt_queue
        self.subtitle_callback = subtitle_callback
        self.error_callback = error_callback
        self._stop_event = threading.Event()
        
        self.recognizer = sr.Recognizer()
        self.translator = GoogleTranslator(source='en', target='es') if GoogleTranslator else None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_PROCESSING)
        
    def stop(self) -> None:
        self._stop_event.set()
        self.executor.shutdown(wait=False)

    def _process_audio_task(self, wav_bytes: bytes) -> None:
        try:
            if not self.translator:
                if self.error_callback:
                    self.error_callback("deep-translator no instalado. Ejecuta: pip install deep-translator")
                return
            
            audio_file = io.BytesIO(wav_bytes)
            with sr.AudioFile(audio_file) as source:
                audio_data = self.recognizer.record(source)

            try:
                english_text = self.recognizer.recognize_google(audio_data, language="en-US")
            except sr.UnknownValueError:
                return
            except sr.RequestError as e:
                if self.error_callback:
                    self.error_callback(f"Error STT: {e}")
                return

            english_text = normalize_text(english_text)
            if not is_valid_text(english_text):
                return

            try:
                spanish_text = self.translator.translate(english_text)
                spanish_text = normalize_text(spanish_text)
                
                if is_valid_text(spanish_text):
                    logger.info(f"Subtítulo generado: {spanish_text}")
                    self.subtitle_callback(spanish_text)
            except Exception as e:
                if self.error_callback:
                    self.error_callback(f"Error de traducción: {e}")

        except Exception as e:
            logger.error(f"Excepción inesperada en _process_audio_task: {e}")

    def run(self) -> None:
        logger.info("TranscriptionWorker iniciado (ThreadPoolExecutor).")
        while not self._stop_event.is_set():
            try:
                wav_bytes = self.stt_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if not wav_bytes:
                continue

            self.executor.submit(self._process_audio_task, wav_bytes)
                
        logger.info("TranscriptionWorker finalizado.")
