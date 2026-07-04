# Arquitectura de Interview Copilot v2.0

Este documento detalla las decisiones de diseño, la estructura concurrente y la gestión avanzada de contexto en **Interview Copilot**.

---

## 1. Clasificador Dinámico (Pre-flight Routing)
Antes de llamar al modelo principal, el sistema intercepta la transcripción de audio y ejecuta una clasificación veloz en segundo plano para determinar el tipo de pregunta en una de 6 categorías (*Algoritmos, System Design, Behavioral, Inglés, OOP, SQL*). Con base en esto, inyecta un System Prompt altamente especializado (definido en `prompts.py`), asegurando respuestas con el enfoque y método correctos (ej. STAR method para Behavioral).

## 2. Patrón Dual-Buffer y Detección Automática
- **TranscriptionWorker:** Consume `stt_queue` para subtítulos en vivo.
- **GeminiWorker (AI):** Consume `audio_queue`. Implementa una heurística inteligente para ignorar "ruido" o frases de menos de 4 palabras localmente. Analiza el audio y genera respuestas automáticamente al detectar el fin de una oración estructurada o cuando se presiona el botón, optimizando los llamados a la API.

## 3. Memoria Persistente (SQLite)
El contexto a corto plazo se maneja con una base de datos local `interviews.db` a través de `memory.py`. 
- Todas las interacciones se guardan con timestamp, categoría, pregunta y respuesta.
- El Worker lee el historial reciente limitando a ~2000 tokens antes de generar la siguiente respuesta para tener total conciencia contextual.

## 4. Contexto de Código (Integración VS Code)
Para el contexto de programación, el sistema lee de manera pasiva y autónoma un archivo local `.vscode_state.json` (creado mediante una extensión local o un watcher). Esto prioriza y sincroniza la vista del Copilot con exactamente el mismo archivo o fragmento que estés mirando en VS Code.

## 5. RAG y Contexto Multidimensional
El sistema (`config.py`) consolida todos los documentos `.md` dentro de la carpeta `context/` (por ejemplo, tu CV, información de la empresa, notas personales, descripción del cargo) y los empaqueta estructuradamente como contexto nativo en cada respuesta, haciendo a la IA experta en tu perfil y la empresa a la que aplicas.

## 6. Interfaz: Modern Overlay en PySide6
Reestructurado para mostrar "tarjetas" translúcidas y flotantes mediante HTML y CSS renderizados en Qt.
- Utiliza flags de *FramelessWindowHint* y *WindowStaysOnTopHint*.
- Parseador de HTML que oculta texto irrelevante y presenta la información de forma limpia dividida en una tarjeta superior (`Question / Context`) y una inferior iluminada (`Suggested Answer`).
- `Stealth Mode` habilitado a nivel OS para que ninguna herramienta de screen sharing detecte la app.

## 7. AI Coach
Un módulo especializado (`coach.py`) invocable desde la interfaz que consulta la base de datos SQLite con la transcripción entera, evalúa tu desempeño con un LLM de evaluación crítica (midiendo Claridad, Ejemplos y Precisión Técnica), y devuelve un diagnóstico para pulir tus habilidades comunicativas.
