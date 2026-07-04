# Arquitectura de Interview Copilot

Este documento detalla las decisiones de diseño, la estructura concurrente y la gestión de la interfaz de usuario en el proyecto **Interview Copilot**.

---

## 1. Patrón Dual-Buffer (Audio Optimizado)

El procesamiento de audio está diseñado para equilibrar la latencia de subtítulos vs. el contexto en el motor de respuestas.

```text
MIC / WASAPI ────> AudioCapture (Thread)
                          │
         ┌────────────────┴───────────────┐
         ▼                                ▼
[ Buffer Subtítulos ]              [ Buffer OpenRouter AI ]
(Fragmentos cortos 2.5s)           (Fragmentos max 10.0s / silencio 1.0s)
         │                                │
         ▼                                ▼
TranscriptionWorker (STT)          GeminiWorker (AI)
```

- **TranscriptionWorker:** Consume `stt_queue`. Al ser fragmentos muy cortos, permite que los subtítulos fluyan rápidamente por la pantalla (STT + Deep Translator sin filtros agresivos destructivos).
- **GeminiWorker (AI):** Consume `audio_queue`. Recientemente optimizado para cortar cuando detecta `1.0s` de silencio o un máximo de `10.0s` de habla continua. Mantiene la continuidad de los buffers históricos durante las transiciones para evitar pérdida de palabras.

---

## 2. Memoria Conversacional a Corto Plazo (Sliding Window)

Dado que `GeminiWorker` procesa fragmentos de audio de forma aislada, se implementó un búfer circular en memoria para otorgarle contexto histórico sin exceder los límites de tokens ni sacrificar velocidad.

- El **Worker mantiene un estado** (`self.memory_buffer`) que almacena el historial de conversación dinámicamente limitándolo a un máximo de ~2000 tokens estimados, optimizando la cantidad de turnos recordados según la longitud de las respuestas.
- Como el modelo genera una estructura `[ESPAÑOL] (resumen de la pregunta) + [INGLÉS] (respuesta danda)`, el búfer funciona como un registro cronológico perfecto del estado de la entrevista.
- Este historial se inyecta dinámicamente bajo el bloque `PAST CONVERSATION CONTEXT` antes de enviar el prompt a la API de OpenRouter.

---

## 3. Espacio de Código Persistente (Estado Inyectado)

Para entrevistas técnicas, la interfaz ahora cuenta con un `QSplitter` que separa el guion de chat de un **Editor de Código Persistente** en el panel derecho.

1. La interfaz extrae automáticamente bloques etiquetados como `[CÓDIGO]...[/CÓDIGO]` provenientes de la IA y actualiza el panel derecho (`self.code_area`).
2. La interfaz mantiene un estado seguro del código (`self.current_code_state`) protegido con un `threading.Lock()` para prevenir "race conditions".
3. El Worker solicita este código actual de forma segura vía `callback` justo antes de hacer una petición y lo inyecta en el prompt como `CURRENT WORKSPACE CODE STATE`.
4. Esto permite a la IA modificar, arreglar o continuar programando sobre el mismo fragmento de código sin tener "amnesia" del estado previo.

---

## 4. Visión Artificial (Multimodalidad Asíncrona)

Cuando el usuario presiona el botón `📷`:
1. La UI (PySide6) se oculta instantáneamente (evitando aparecer en la captura).
2. Se procesan los eventos de Qt y se toma un pantallazo usando `Pillow (ImageGrab)`.
3. La imagen se inyecta en `image_queue`.
4. **Novedad:** El bucle de ejecución de `GeminiWorker` ahora sondea continuamente ambas colas (`audio_queue` y `image_queue`) sin bloquearse exclusivamente en el audio. Si detecta una imagen, incluso en silencio absoluto de voz, compone un payload y llama a OpenRouter inmediatamente.

---

## 5. Interfaz de Usuario (HUD Overlay en PySide6)

PySide6 garantiza un diseño robusto similar a un "HUD de videojuego".

### Flags Críticas de Qt
- **`Qt.FramelessWindowHint`**: Quita la barra de título tradicional de Windows.
- **`Qt.WindowStaysOnTopHint`**: Overlay puro, siempre visible.
- **`Qt.WindowDoesNotAcceptFocus`**: La aplicación se vuelve 100% pasiva a nivel sistema. Un clic accidental en el Copilot no desvía el cursor del teclado del editor de código o navegador.
- **`Qt.WA_TranslucentBackground`**: Permite un fondo cristalino (`rgba`).

### Seguridad de Hilos (Signals & Slots)
Puesto que los workers viven en hilos paralelos (`threading.Thread`), modificar la UI de PySide6 directamente causaría un *Segfault*. Usamos el patrón `QObject` en la UI (`WorkerSignals`), para que los hilos emitan señales que el hilo principal captura y renderiza de forma segura.

---

## 6. Stealth Mode y Ejecutable VBS

- **Stealth Mode:** Extraemos el Window Handle (`winId`) y usamos la API de Windows `SetWindowDisplayAffinity(0x00000011)`. Zoom o Teams ignorarán la ventana.
- **Lanzador (VBScript):** El archivo `LanzarCopilot.vbs` invoca `pythonw.exe`, ejecutando la aplicación de manera invisible sin abrir ninguna consola negra. Para que el usuario cierre el proceso correctamente en la terminal, se atrapó globalmente la señal `SIGINT` en la UI.
- **Atajo Global:** Se usa `keyboard` (`Ctrl+Shift+H`) para ocultar/mostrar el HUD sin importar qué app tenga el foco.

---

## 7. Ingeniería de Prompts

El `SYSTEM_PROMPT` (en `copilot/config.py`) fuerza la siguiente estructura para facilitar la lectura fluida del candidato:
- Extrae un resumen rápido en `[ESPAÑOL]` para dar contexto.
- Genera ÚNICAMENTE el guion en `[INGLÉS]`, escrito en primera persona y sin explicaciones extra (evitando el formato STAR o respuestas verbosas) para ser leído de inmediato.
- Si hay requerimientos de programación, envuelve la solución técnica en el bloque `[CÓDIGO]` sin usar formato markdown extra.
