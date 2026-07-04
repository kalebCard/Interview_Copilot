# Interview Copilot

> Asistente de entrevistas técnicas en tiempo real, impulsado por **OpenRouter**, **PySide6** y **Visión Artificial**.
> Captura el audio del sistema y la pantalla, te muestra **subtítulos en vivo**, y te da respuestas directas como un guion de lectura rápida con RAG avanzado, todo con memoria persistente y baja latencia.

---

## Características Principales

1. **Sistema RAG Multidimensional:** Crea una carpeta `data/context/` con tu CV, Info de la Empresa y la Descripción del Trabajo. Copilot lo consumirá para darte respuestas increíblemente personalizadas a cada vacante.
2. **Enrutador de IA Predictivo:** Clasifica cada pregunta antes de responder (Behavioral, Algoritmos, System Design) y cambia el System Prompt dinámicamente para dar la respuesta perfecta (ej. aplicando método STAR).
3. **Integración Silenciosa con VS Code:** Lee pasivamente `data/.vscode_state.json` para tener conciencia en vivo del archivo de código exacto en el que tienes el cursor.
4. **Memoria Persistente y AI Coach:** Guarda cada sesión en `data/interviews.db` (SQLite). Al terminar, presiona el botón "Coach" para recibir feedback analítico sobre tu claridad y ejemplos.
5. **Detección Automática y Overlay Moderno:** Heurísticas de ruido ahorran llamadas a la API y autodetectan preguntas largas, disparando la respuesta visualmente en "tarjetas" transparentes que flotan sobre todo. No roba foco y es 100% invisible para Zoom y Teams.

---

## Estructura del proyecto

```text
├── copilot/             # Paquete principal modular
│   ├── core/            # Lógica central (AppController, Memoria, Settings, LLM Client, Config)
│   ├── services/        # Workers de fondo (Audio, Gemini, STT, Coach, VSCode)
│   └── ui/              # Componentes visuales PySide6 (MainWindow, Theme, TitleBar, SettingsDialog)
├── data/                # Carpeta generada (Logs, BD, Configuraciones y Contexto)
│   ├── context/         # Carpeta de contexto RAG (pon tu resume.md y otros .md aquí)
│   ├── interviews.db    # Base de datos SQLite
│   ├── settings.json    # Configuraciones de UI guardadas
│   └── copilot.log      # Registro de la aplicación
├── main.py              # Puerta de entrada en consola
├── LanzarCopilot.vbs    # Ejecutable invisible que lanza la App sin terminal
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
- **Configuración (⚙):** Abre un panel para personalizar el Modelo de IA, los umbrales de audio (VAD) y los atajos del teclado (Hotkeys).
- **Gemini AI / Iniciar IA:** Enciende el motor de análisis profundo. Usa el WASAPI Loopback automático.
- **Subtítulos:** Enciende el motor rápido de transcripción.
- **(Cámara):** Captura tu pantalla al instante. Ideal si el entrevistador te pide resolver un algoritmo visualmente.
- **Atajos personalizables:** Puedes configurar teclas para iniciar/detener la IA, los subtítulos, capturar la pantalla y mostrar/ocultar el HUD (por defecto `Ctrl + Shift + H`).

---

## 📖 Arquitectura
Consulta el archivo [`ARCHITECTURE.md`](ARCHITECTURE.md) para entender el sistema de Memoria a Corto Plazo, el estado del Código Persistente y el Dual-Buffer VAD.

---

## 📄 Licencia

Este proyecto está distribuido bajo la licencia **GNU Affero General Public License v3.0 (AGPL v3)** - mira el archivo [LICENSE](LICENSE) para más detalles.

Copyright (c) 2026 Kaleb Cardona
