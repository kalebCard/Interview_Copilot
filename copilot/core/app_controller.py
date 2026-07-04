import queue
import threading
from typing import Callable, Optional
from copilot.core.logger import get_logger
from copilot.services.audio import AudioCapture
from copilot.services.worker import GeminiWorker
from copilot.services.translator import TranscriptionWorker
from copilot.services.vscode import read_vscode_state
from copilot.core.config import load_context

logger = get_logger(__name__)

class AppController:
    def __init__(
        self,
        gemini_result_cb: Callable[[str], None],
        gemini_error_cb: Callable[[str], None],
        stt_result_cb: Callable[[str], None],
        stt_error_cb: Callable[[str], None],
        status_update_cb: Callable[[str, str], None]
    ):
        self.gemini_result_cb = gemini_result_cb
        self.gemini_error_cb = gemini_error_cb
        self.stt_result_cb = stt_result_cb
        self.stt_error_cb = stt_error_cb
        self.status_update_cb = status_update_cb

        self.audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=2)
        self.stt_queue: queue.Queue[bytes] = queue.Queue(maxsize=10)
        self.image_queue: queue.Queue[object] = queue.Queue(maxsize=1)

        self.audio_thread: Optional[AudioCapture] = None
        self.gemini_thread: Optional[GeminiWorker] = None
        self.transcription_thread: Optional[TranscriptionWorker] = None
        
        self.is_running_stt = False
        self.is_running_ai = False
        
        self.current_code_state = ""
        self.code_state_lock = threading.Lock()
        
        self.context_content = load_context()

    def get_code_state_safe(self) -> str:
        vscode_state = read_vscode_state()
        with self.code_state_lock:
            if vscode_state:
                return vscode_state
            return self.current_code_state

    def set_code_state_safe(self, code: str):
        with self.code_state_lock:
            self.current_code_state = code

    def ensure_audio_capture(self, device_idx: Optional[int]):
        if self.audio_thread is not None and self.audio_thread.is_alive():
            return
            
        self.audio_thread = AudioCapture(
            ai_queue=self.audio_queue,
            stt_queue=self.stt_queue,
            device_index=device_idx,
            status_callback=lambda msg: self.status_update_cb(msg, "running"),
            error_callback=self.gemini_error_cb
        )
        self.audio_thread.start()

    def check_audio_capture_stop(self):
        if not self.is_running_ai and not self.is_running_stt:
            self.status_update_cb("Listo", "idle")
            with self.code_state_lock:
                if self.audio_thread:
                    self.audio_thread.stop()
                    self.audio_thread.join(timeout=2)
                    self.audio_thread = None

    def start_stt(self, device_idx: Optional[int]):
        self.ensure_audio_capture(device_idx)
        self.is_running_stt = True

        self.transcription_thread = TranscriptionWorker(
            stt_queue=self.stt_queue,
            subtitle_callback=self.stt_result_cb,
            error_callback=self.stt_error_cb
        )
        self.transcription_thread.start()

    def stop_stt(self):
        self.is_running_stt = False
        if self.transcription_thread:
            self.transcription_thread.stop()
            self.transcription_thread.join(timeout=2)
            self.transcription_thread = None
        self.check_audio_capture_stop()

    def start_ai(self, api_key: str, model_name: str, device_idx: Optional[int]):
        if not api_key:
            self.gemini_error_cb("No se encontró OPENROUTER_API_KEY en .env")
            return

        self.ensure_audio_capture(device_idx)
        self.is_running_ai = True

        self.gemini_thread = GeminiWorker(
            audio_queue=self.audio_queue,
            image_queue=self.image_queue,
            api_key=api_key,
            result_callback=self.gemini_result_cb,
            error_callback=self.gemini_error_cb,
            context_content=self.context_content,
            model_name=model_name,
            get_code_state_callback=self.get_code_state_safe,
            chunk_callback=None
        )
        self.gemini_thread.start()

    def stop_ai(self):
        self.is_running_ai = False
        if self.gemini_thread:
            self.gemini_thread.stop()
            self.gemini_thread.join(timeout=2)
            self.gemini_thread = None
        self.check_audio_capture_stop()

    def stop_all(self):
        if self.is_running_ai:
            self.stop_ai()
        if self.is_running_stt:
            self.stop_stt()

    def capture_screen(self):
        if not self.is_running_ai:
            self.status_update_cb("Enciende Gemini AI primero", "error")
            return False
            
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=True)
            if self.image_queue.full():
                try:
                    self.image_queue.get_nowait()
                except queue.Empty:
                    pass
            self.image_queue.put(img)
            self.status_update_cb("Captura enviada a Gemini", "running")
            return True
        except Exception as e:
            self.gemini_error_cb(f"Error al capturar: {e}")
            return False

    def run_coach(self, report_cb: Callable[[str], None]):
        def run():
            from copilot.services.coach import generate_coach_report
            report = generate_coach_report("default_session")
            report_cb(report)
        threading.Thread(target=run, daemon=True).start()
