# Interview Copilot

> Asistente de entrevistas técnicas en tiempo real, impulsado por **OpenRouter**, **PySide6** y **Visión Artificial**.
> Captura el audio del sistema y la pantalla, te muestra **subtítulos traducidos al instante**, un **espacio de trabajo de código persistente** y te da respuestas directas como un guion de lectura rápida, todo con memoria conversacional y baja latencia.

---

## Características Principales

1. **Inteligencia Multimodal (Visión + Audio):** Analiza lo que escuchas y lo que ves. Pulsa el botón `📷` para enviar un pantallazo silencioso a la IA cuando te muestren código o diagramas. Funciona incluso si estás en silencio total.
2. **Espacio de Código Persistente & Memoria:** Panel de doble vista. A la derecha, la IA puede escribir, recordar y modificar código (gracias a la inyección de estado). La memoria integrada ("Sliding Window") recuerda los últimos 6 turnos de conversación para nunca perder el hilo.
3. **Overlay HUD 100% Invisible (Stealth Mode):** La interfaz está construida con **PySide6**. Flota sobre tu pantalla con fondo semitransparente, **NO roba el foco de tu teclado** y es completamente **invisible** al compartir pantalla por Zoom o Teams.
4. **Respuesta Rápida y Limpia:** Los subtítulos en vivo saltan cada pocos segundos. El audio de análisis se envía optimizado (corte inteligente de silencios a 1.0s y max 10.0s) a la API de OpenRouter, entregando respuestas listas para leer en voz alta sin verbosidad.
5. **Completamente Desconectado de Google SDK:** Usa el paquete nativo de `openai` apuntando a OpenRouter para la máxima compatibilidad de modelos y menor latencia de conexión.

---

## Estructura del proyecto

```text
ENTREVISTAS_COPILOT/
├── copilot/             # Paquete principal con la lógica modular
│   ├── __init__.py
│   ├── config.py        # Configuración, .env, y Prompt de Memoria/Guion
│   ├── audio.py         # Dual Buffer, WASAPI loopback y VAD (Optimizados a 1s)
│   ├── translator.py    # STT de baja latencia (Subtítulos)
│   ├── worker.py        # Procesamiento OpenRouter, Memoria FIFO y Estado
│   ├── check.py         # Validación del entorno CLI
│   └── ui.py            # Interfaz gráfica (PySide6, QSplitter, Signals/Slots, QSS)
├── main.py              # Puerta de entrada en consola
├── LanzarCopilot.vbs    # Ejecutable invisible que lanza la App sin terminal
├── hoja_de_vida.md      # Tu CV — se inyecta como contexto base
├── requirements.txt     # Dependencias Python
└── ARCHITECTURE.md      # Detalles profundos del diseño interno
```

---

## Requisitos y Dependencias

- **Python 3.10+** (Windows 10/11 requerido para WASAPI Loopback).
- API Key de OpenRouter → [Obtenerla aquí](https://openrouter.ai/). (Se configura en el `.env` como `OPENROUTER_API_KEY`).

Instalación:
```bash
pip install -r requirements.txt
```

Dependencias clave instaladas:
- `openai` (Cliente compatible para OpenRouter)
- `PySide6` (Interfaz gráfica moderna)
- `Pillow` (Visión artificial / Capturas)
- `keyboard` (Atajos globales)
- `PyAudioWPatch` (Captura WASAPI Loopback)
- `SpeechRecognition` y `deep-translator` (Subtítulos en tiempo real)

---

## Uso

Recomendado: Dale doble clic al archivo **`LanzarCopilot.vbs`**. Lanzará la interfaz gráfica directamente de manera limpia, sin consola de comandos parpadeando detrás.

Alternativa por consola:
```bash
# Lanzar el HUD
python main.py

# Validar tu configuración
python main.py --check
```

### Controles
- **Arrastrar:** Haz clic y arrastra desde la barra superior.
- **Selector de Modelo:** Escoge en tiempo real entre distintos niveles de inteligencia (Gemini Flash/Pro, Claude Sonnet/Opus).
- **Gemini AI / Iniciar IA:** Enciende el motor de análisis profundo.
- **Subtítulos:** Enciende el motor rápido de transcripción.
- **(Cámara):** Captura tu pantalla al instante. Ideal si el entrevistador te pide resolver un algoritmo visualmente.
- **Ctrl + Shift + H:** Oculta/Muestra el panel completo sin perder foco.

---

## 📖 Arquitectura
Consulta el archivo [`ARCHITECTURE.md`](ARCHITECTURE.md) para entender el sistema de Memoria a Corto Plazo, el estado del Código Persistente y el Dual-Buffer VAD.
