
import threading
import queue
import io
import re
import speech_recognition as sr
from deep_translator import GoogleTranslator
from copilot.logger import get_logger
from typing import Callable, Optional, List

logger = get_logger(__name__)

MAX_CONCURRENT_PROCESSING = 3

BANNED_PATTERNS = [
    r"\bnigg[aer]s?\b", r"\bchild(ren)?\b", r"\bkid(s)?\b", r"\bminor(s)?\b",
    r"\bteen(s|ager|agers)?\b", r"\bbaby\b", r"\btoddler(s)?\b", r"\byoungster(s)?\b",
    r"\bschool\b", r"\bstudent(s)?\b", r"\bage\s?\d+\b"
]
BANNED_REGEX = re.compile("|".join(BANNED_PATTERNS), re.IGNORECASE)

def split_text(text: str, max_chars: int = 30) -> List[str]:
    if not text or max_chars <= 0:
        return []
    words = text.split()
    chunks = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current += " " + word if current else word
        else:
            if current:
                chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks

def remove_banned_words(text: str) -> str:
    if not text:
        return ""
    cleaned = BANNED_REGEX.sub("", text)
    return re.sub(r"\s{2,}", " ", cleaned).strip()

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
        
        self.active_threads = 0
        self.thread_count_lock = threading.Lock()
        
    def stop(self) -> None:
        self._stop_event.set()

    def _process_audio_task(self, wav_bytes: bytes) -> None:
        try:

            recognizer = sr.Recognizer()
            translator = GoogleTranslator(source='en', target='es')
            
            audio_file = io.BytesIO(wav_bytes)
            with sr.AudioFile(audio_file) as source:
                audio_data = recognizer.record(source)

            try:
                english_text = recognizer.recognize_google(audio_data, language="en-US")
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
                spanish_text = translator.translate(english_text)
                spanish_text = normalize_text(spanish_text)
                spanish_text = remove_banned_words(spanish_text)
                
                if is_valid_text(spanish_text):
                    logger.info(f"Subtítulo generado: {spanish_text}")
                    self.subtitle_callback(spanish_text)
            except Exception as e:
                if self.error_callback:
                    self.error_callback(f"Error de traducción: {e}")

        except Exception as e:
            logger.error(f"Excepción inesperada en _process_audio_task: {e}")
        finally:
            with self.thread_count_lock:
                self.active_threads -= 1

    def run(self) -> None:
        logger.info("TranscriptionWorker iniciado (Concurrente).")
        while not self._stop_event.is_set():

            with self.thread_count_lock:
                current_active = self.active_threads
                
            if current_active >= MAX_CONCURRENT_PROCESSING:
                self._stop_event.wait(0.05)
                continue

            try:
                wav_bytes = self.stt_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if not wav_bytes:
                continue

            with self.thread_count_lock:
                self.active_threads += 1
            
            t = threading.Thread(target=self._process_audio_task, args=(wav_bytes,), daemon=True)
            t.start()
                
        logger.info("TranscriptionWorker finalizado.")
