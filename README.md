# Interview Copilot

> Asistente de entrevistas técnicas en tiempo real, impulsado por **OpenRouter**, **PySide6** y **Visión Artificial**.
> Captura el audio del sistema y la pantalla, te muestra **subtítulos en vivo**, y te da respuestas directas como un guion de lectura rápida con RAG avanzado, todo con memoria persistente y baja latencia.

---

## Características Principales

1. **Sistema RAG Multidimensional:** Crea una carpeta `context/` con tu CV, Info de la Empresa y la Descripción del Trabajo. Copilot lo consumirá para darte respuestas increíblemente personalizadas a cada vacante.
2. **Enrutador de IA Predictivo:** Clasifica cada pregunta antes de responder (Behavioral, Algoritmos, System Design) y cambia el System Prompt dinámicamente para dar la respuesta perfecta (ej. aplicando método STAR).
3. **Integración Silenciosa con VS Code:** Lee pasivamente `.vscode_state.json` para tener conciencia en vivo del archivo de código exacto en el que tienes el cursor.
4. **Memoria Persistente y AI Coach:** Guarda cada sesión en `interviews.db` (SQLite). Al terminar, presiona el botón "Coach" para recibir feedback analítico sobre tu claridad y ejemplos.
5. **Detección Automática y Overlay Moderno:** Heurísticas de ruido ahorran llamadas a la API y autodetectan preguntas largas, disparando la respuesta visualmente en "tarjetas" transparentes que flotan sobre todo. No roba foco y es 100% invisible para Zoom y Teams.

---

## Estructura del proyecto


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

---

## 📄 Licencia

Este proyecto está distribuido bajo la licencia **GNU Affero General Public License v3.0 (AGPL v3)** - mira el archivo [LICENSE](LICENSE) para más detalles.

Copyright (c) 2026 Kaleb Cardona
