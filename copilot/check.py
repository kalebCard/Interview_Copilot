
import os
from pathlib import Path

from copilot.config import RESUME_FILENAME, load_resume

def run_check() -> None:
    print("\n===========================================")
    print("  Interview Copilot -- Startup Check")
    print("===========================================\n")

    all_ok = True

    resume = load_resume()
    if "WARNING" in resume:
        print(f"  [WARN]  {RESUME_FILENAME} no encontrado en {Path.cwd()}")
        all_ok = False
    else:
        print(f"  [OK]    {RESUME_FILENAME} cargado ({len(resume)} caracteres)")

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    key_name = "OPENROUTER_API_KEY"

    if api_key:
        print(f"  [OK]    {key_name} está configurada")
    else:
        print(f"  [WARN]  {key_name} no configurada — edita el archivo .env")
        all_ok = False

    try:
        import pyaudiowpatch as pyaudio
        pa = pyaudio.PyAudio()
        n_devices = pa.get_device_count()
        pa.terminate()
        print(f"  [OK]    PyAudio disponible ({n_devices} dispositivos de audio)")
        pa2 = pyaudio.PyAudio()
        try:
            wasapi = pa2.get_host_api_info_by_type(pyaudio.paWASAPI)
            print(f"  [OK]    WASAPI loopback soportado (índice API: {wasapi['index']})")
        except Exception:
            print("  [WARN]  WASAPI no disponible — se usará el micrófono")
        pa2.terminate()
    except ImportError:
        print("  [FAIL]  PyAudio no instalado  ->  pip install PyAudioWPatch")
        all_ok = False
    except Exception as exc:
        print(f"  [FAIL]  Error de PyAudio: {exc}")
        all_ok = False

    try:
        import openai
        print("  [OK]    openai SDK disponible (OpenRouter)")
    except ImportError:
        print("  [FAIL]  openai no instalado  ->  pip install openai")
        all_ok = False

    print()
    if all_ok:
        print("  [OK] Todo listo. Ejecuta: python main.py")
    else:
        print("  [!!] Hay problemas. Corrígelos y vuelve a ejecutar: python main.py")
    print()
