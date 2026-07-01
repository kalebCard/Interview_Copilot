
import threading
import array
import queue
import wave
from io import BytesIO
from collections import deque
from typing import Optional, Callable

from copilot.config import (
    VAD_BLOCK_DURATION,
    VAD_SILENCE_TIMEOUT,
    VAD_MAX_DURATION,
    VAD_MAX_DURATION_STT,
    SILENCE_THRESHOLD,
    SAMPLE_RATE,
)
from copilot.logger import get_logger

logger = get_logger(__name__)

def pcm_to_wav(raw_pcm: bytes, sample_rate: int, channels: int) -> bytes:
    if channels > 2:
        try:
            pcm_array = array.array('h', raw_pcm)
            mono_array = pcm_array[::channels]
            raw_pcm = mono_array.tobytes()
            channels = 1
        except Exception as e:
            logger.error(f"Error downmixing audio: {e}")

    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_pcm)
    return buf.getvalue()

class AudioCapture(threading.Thread):
    def __init__(
        self,
        ai_queue: Optional["queue.Queue[bytes]"],
        stt_queue: Optional["queue.Queue[bytes]"],
        device_index: Optional[int] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(daemon=True, name="AudioCaptureThread")
        self.ai_queue       = ai_queue
        self.stt_queue      = stt_queue
        self.device_index   = device_index
        self.status_callback = status_callback
        self.error_callback  = error_callback
        self._stop_event    = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def _notify_status(self, msg: str) -> None:
        if self.status_callback:
            self.status_callback(msg)

    def _notify_error(self, msg: str) -> None:
        if self.error_callback:
            self.error_callback(msg)

    def run(self) -> None:
        try:
            import pyaudiowpatch as pyaudio
        except ImportError:
            self._notify_error("PyAudio no instalado. Ejecuta: pip install PyAudioWPatch")
            return

        pa = pyaudio.PyAudio()
        stream = None
        use_loopback = False

        try:
            device_idx = self.device_index

            if device_idx is None:
                try:
                    default_loopback = pa.get_default_wasapi_loopback()
                    device_idx = default_loopback["index"]
                    use_loopback = True
                    self._notify_status("WASAPI loopback detectado automáticamente")
                except Exception:
                    try:
                        device_idx = pa.get_default_input_device_info()["index"]
                    except Exception:
                        device_idx = 0
                    use_loopback = False
                    self._notify_status("Usando micrófono (WASAPI loopback no disponible)")

            dev_info        = pa.get_device_info_by_index(device_idx)
            actual_rate     = int(dev_info.get("defaultSampleRate", SAMPLE_RATE))
            max_channels    = int(dev_info.get("maxInputChannels") or 0)
            actual_channels = max_channels if max_channels > 0 else 1

            open_kwargs = dict(
                format=pyaudio.paInt16,
                channels=actual_channels,
                rate=actual_rate,
                input=True,
                input_device_index=device_idx,
                frames_per_buffer=1024,
            )

            stream = pa.open(**open_kwargs)
            mode_label = "Loopback" if use_loopback else "Mic"
            self._notify_status(
                f"Capturando — {actual_rate}Hz / {actual_channels}ch / {mode_label}"
            )

            frames_per_block = int(VAD_BLOCK_DURATION * actual_rate)
            silence_timeout_blocks = int(VAD_SILENCE_TIMEOUT / VAD_BLOCK_DURATION)
            stt_silence_timeout_blocks = int(0.7 / VAD_BLOCK_DURATION)
            max_blocks_ai = int(VAD_MAX_DURATION / VAD_BLOCK_DURATION)
            max_blocks_stt = int(VAD_MAX_DURATION_STT / VAD_BLOCK_DURATION)
            
            audio_buffer_ai: list[bytes] = []
            audio_buffer_stt: list[bytes] = []
            silence_blocks_count = 0
            speech_active = False
            stt_flushed = False

            while not self._stop_event.is_set():
                collected_frames: list[bytes] = []
                frames_collected = 0

                while frames_collected < frames_per_block and not self._stop_event.is_set():
                    to_read = min(1024, frames_per_block - frames_collected)
                    try:
                        data = stream.read(to_read, exception_on_overflow=False)
                    except OSError as read_err:
                        self._notify_error(f"Error de lectura de audio: {read_err}")
                        break
                    collected_frames.append(data)
                    frames_collected += to_read

                if not collected_frames or self._stop_event.is_set():
                    break
                    
                raw_pcm = b"".join(collected_frames)
                
                if len(raw_pcm) % 2 != 0:
                    raw_pcm = raw_pcm[:-1]
                
                pcm_array = array.array('h', raw_pcm)
                peak_amplitude = max(abs(max(pcm_array)), abs(min(pcm_array))) if pcm_array else 0
                
                is_silence = peak_amplitude < SILENCE_THRESHOLD

                if not is_silence:
                    if not speech_active:
                        logger.debug(f"Inicio de voz detectado (pico: {peak_amplitude}).")
                    speech_active = True
                    stt_flushed = False
                    silence_blocks_count = 0
                    audio_buffer_ai.append(raw_pcm)
                    audio_buffer_stt.append(raw_pcm)
                else:
                    if speech_active:
                        silence_blocks_count += 1
                        audio_buffer_ai.append(raw_pcm)
                        if not stt_flushed:
                            audio_buffer_stt.append(raw_pcm)
                            
                        if silence_blocks_count >= stt_silence_timeout_blocks and not stt_flushed:
                            if self.stt_queue and audio_buffer_stt:
                                wav_stt = pcm_to_wav(b"".join(audio_buffer_stt), actual_rate, actual_channels)
                                try:
                                    self.stt_queue.put_nowait(wav_stt)
                                except queue.Full:
                                    pass
                            audio_buffer_stt = []
                            stt_flushed = True
                        
                        if silence_blocks_count >= silence_timeout_blocks:

                            if self.ai_queue and audio_buffer_ai:
                                duration = len(audio_buffer_ai) * VAD_BLOCK_DURATION
                                logger.debug(f"Fin de voz detectado. Enviando chunk AI de {duration:.1f}s.")
                                wav_ai = pcm_to_wav(b"".join(audio_buffer_ai), actual_rate, actual_channels)
                                try:
                                    self.ai_queue.put_nowait(wav_ai)
                                except queue.Full:
                                    pass
                            
                            audio_buffer_ai = []
                            audio_buffer_stt = []
                            speech_active = False
                            stt_flushed = False
                            silence_blocks_count = 0
                    else:

                        audio_buffer_ai = [raw_pcm]
                        audio_buffer_stt = [raw_pcm]
                        
                if len(audio_buffer_stt) >= max_blocks_stt and speech_active:
                    if self.stt_queue:
                        wav_stt = pcm_to_wav(b"".join(audio_buffer_stt), actual_rate, actual_channels)
                        try:
                            self.stt_queue.put_nowait(wav_stt)
                        except queue.Full:
                            pass
                    audio_buffer_stt = []

                if len(audio_buffer_ai) >= max_blocks_ai and speech_active:
                    if self.ai_queue:
                        logger.debug(f"Máxima duración alcanzada. Forzando envío AI de {VAD_MAX_DURATION}s.")
                        wav_ai = pcm_to_wav(b"".join(audio_buffer_ai), actual_rate, actual_channels)
                        try:
                            self.ai_queue.put_nowait(wav_ai)
                        except queue.Full:
                            pass
                    audio_buffer_ai = []

        except Exception as exc:
            self._notify_error(f"Error de captura de audio: {exc}")
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            pa.terminate()
            logger.info("AudioCapture finalizado.")
