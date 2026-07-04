import pytest
import queue
from copilot.services.audio import VADProcessor
from copilot.core.config import SAMPLE_RATE

def test_vad_process_frame_silence():
    ai_queue = queue.Queue()
    stt_queue = queue.Queue()
    
    vad = VADProcessor(ai_queue, stt_queue, SAMPLE_RATE, 1)
    
    # Frame that has very low amplitude, representing silence
    silent_frame = b'\x00' * 1024
    
    vad.process_frame(silent_frame)
    
    assert vad.speech_active is False
    assert vad.silence_blocks_count == 0

def test_vad_process_frame_noise():
    ai_queue = queue.Queue()
    stt_queue = queue.Queue()
    
    vad = VADProcessor(ai_queue, stt_queue, SAMPLE_RATE, 1)
    
    # Frame that has high amplitude
    noise_frame = b'\xFF\x7F' * 512
    
    vad.process_frame(noise_frame)
    
    assert vad.speech_active is True
