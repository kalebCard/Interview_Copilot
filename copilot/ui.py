
import sys
import os
import signal
import time
import queue
import re
import ctypes
import keyboard
import threading
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTextBrowser, QFrame, QSplitter, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, QObject, Signal

from copilot.config import (
    load_context,
    build_system_prompt,
)
from copilot.audio import AudioCapture
from copilot.worker import GeminiWorker
from copilot.translator import TranscriptionWorker
from copilot.logger import get_logger

logger = get_logger(__name__)

COLORS = {
    "bg":           "#0f1117",
    "surface":      "#1a1d27",
    "surface2":     "#22273a",
    "border":       "#2d3148",
    "accent_blue":  "#38bdf8",
    "accent_amber": "#f59e0b",
    "accent_green": "#22c55e",
    "accent_red":   "#ef4444",
    "text":         "#e2e8f0",
    "text_muted":   "#64748b",
    "title_bar":    "#080b12",
}

MAIN_STYLE = f"""
QMainWindow, QWidget#centralWidget {{
    background-color: rgba(15, 17, 23, 245);
}}
QWidget {{
    color: {COLORS["text"]};
    font-family: "Segoe UI";
}}
QComboBox {{
    background-color: {COLORS["surface2"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 2px 4px;
}}
QComboBox::drop-down {{
    border: none;
}}
QTextBrowser {{
    background-color: rgba(10, 12, 18, 150);
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
}}
QScrollBar:vertical {{
    background-color: {COLORS["bg"]};
    width: 10px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background-color: {COLORS["surface2"]};
    min-height: 20px;
    border-radius: 4px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""

class WorkerSignals(QObject):
    gemini_result = Signal(str)
    gemini_error = Signal(str)
    stt_result = Signal(str)
    stt_error = Signal(str)
    status_update = Signal(str, str)
    toggle_visibility = Signal()

class TitleBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(40)
        self.setStyleSheet("background-color: rgba(8, 11, 18, 220);")
        
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 10, 0)
        layout.setSpacing(6)

        lbl_icon = QLabel("⬡")
        lbl_icon.setStyleSheet(f"color: {COLORS['accent_blue']}; font-size: 16pt;")
        layout.addWidget(lbl_icon)

        lbl_title = QLabel("Interview Copilot")
        lbl_title.setStyleSheet("font-weight: bold; font-size: 10pt;")
        layout.addWidget(lbl_title)


        layout.addStretch()

        self.spinner_label = QLabel("")
        self.spinner_label.setStyleSheet(f"color: {COLORS['accent_blue']}; font-family: Consolas; font-size: 10pt;")
        layout.addWidget(self.spinner_label)

        btn_min = QPushButton("─")
        btn_min.setFixedSize(30, 30)
        btn_min.setCursor(Qt.PointingHandCursor)
        btn_min.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {COLORS["text_muted"]}; border: none; }}
            QPushButton:hover {{ background-color: {COLORS["border"]}; color: white; }}
        """)
        btn_min.clicked.connect(self.parent_window.showMinimized)
        layout.addWidget(btn_min)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 30)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {COLORS["text_muted"]}; border: none; }}
            QPushButton:hover {{ background-color: {COLORS["accent_red"]}; color: white; }}
        """)
        btn_close.clicked.connect(self.parent_window.close)
        layout.addWidget(btn_close)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.parent_window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

class CopilotApp(QMainWindow):
    SPINNER_FRAMES = ["● ○ ○", "○ ● ○", "○ ○ ●", "○ ● ○"]

    def __init__(self):
        super().__init__()

        self.audio_queue = queue.Queue(maxsize=2)
        self.stt_queue = queue.Queue(maxsize=10)
        self.image_queue = queue.Queue(maxsize=1)

        self.audio_thread: Optional[AudioCapture] = None
        self.gemini_thread: Optional[GeminiWorker] = None
        self.transcription_thread: Optional[TranscriptionWorker] = None
        
        self.is_running_stt = False
        self.is_running_ai = False
        self.current_code_state = ""
        self.code_state_lock = threading.Lock()

        self._spinner_idx = 0
        
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self._tick_spinner)

        self.context_content = load_context()

        self.signals = WorkerSignals()
        self.signals.gemini_result.connect(self._display_response)
        self.signals.gemini_error.connect(self._show_error)
        self.signals.stt_result.connect(self._enqueue_subtitle)
        
        self.subtitle_queue_internal = queue.Queue()
        self.karaoke_timer = QTimer(self)
        self.karaoke_timer.setInterval(80)
        self.karaoke_timer.timeout.connect(self._process_subtitle_queue)
        
        self.subtitle_idle_timer = QTimer(self)
        self.subtitle_idle_timer.setInterval(3000)
        self.subtitle_idle_timer.setSingleShot(True)
        self.subtitle_idle_timer.timeout.connect(self._clear_subtitle)
        self.signals.stt_error.connect(self._show_error)
        self.signals.status_update.connect(self._set_status)
        self.signals.toggle_visibility.connect(self._on_toggle_visibility)

        try:
            keyboard.add_hotkey('ctrl+shift+h', lambda: self.signals.toggle_visibility.emit())
        except Exception as e:
            logger.warning(f"No se pudo registrar atajo global: {e}")

        self._configure_window()
        self._build_ui()

    def _get_code_state_safe(self) -> str:
        from copilot.vscode import read_vscode_state
        vscode_state = read_vscode_state()
        
        with self.code_state_lock:
            if vscode_state:
                return vscode_state
            return self.current_code_state

    def _set_code_state_safe(self, code):
        with self.code_state_lock:
            self.current_code_state = code

    def _configure_window(self):
        self.setWindowTitle("Interview Copilot")
        
        flags = (Qt.FramelessWindowHint | 
                 Qt.WindowStaysOnTopHint | 
                 Qt.WindowDoesNotAcceptFocus)
        self.setWindowFlags(flags)
        
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.resize(850, 660)
        self.setMinimumSize(800, 500)
        self.setStyleSheet(MAIN_STYLE)
        
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.width() - self.width() - 16
        y = 40
        self.move(x, y)

        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
            logger.info("Stealth Mode activado.")
        except Exception as e:
            logger.warning(f"No se pudo activar Stealth Mode: {e}")

    def _build_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)
        
        b1 = QFrame()
        b1.setFixedHeight(1)
        b1.setStyleSheet(f"background-color: {COLORS['border']};")
        main_layout.addWidget(b1)

        config_panel = QWidget()
        config_panel.setStyleSheet(f"background-color: {COLORS['surface']};")
        config_layout = QVBoxLayout(config_panel)
        config_layout.setContentsMargins(16, 12, 16, 12)
        
        dev_layout = QHBoxLayout()
        lbl_dev = QLabel("Device")
        lbl_dev.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 9pt;")
        dev_layout.addWidget(lbl_dev)
        
        self.device_combo = QComboBox()
        self.device_combo.addItem("Auto (WASAPI Loopback)")
        self._populate_devices()
        dev_layout.addWidget(self.device_combo, 1)
        config_layout.addLayout(dev_layout)
        
        model_layout = QHBoxLayout()
        lbl_model = QLabel("Modelo IA")
        lbl_model.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 9pt;")
        model_layout.addWidget(lbl_model)
        
        self.model_combo = QComboBox()
        self.model_combo.addItem("1. Rapidez Extrema (Gemini 2.5 Flash)", "google/gemini-2.5-flash")
        self.model_combo.addItem("2. Ágil (Gemini 2.5 Pro)", "google/gemini-2.5-pro")
        self.model_combo.addItem("3. Inteligente (Claude Sonnet 4-6)", "anthropic/claude-sonnet-4-6")
        self.model_combo.addItem("4. Máxima Inteligencia (Claude Opus 4-8)", "anthropic/claude-opus-4-8")
        model_layout.addWidget(self.model_combo, 1)
        config_layout.addLayout(model_layout)
        
        main_layout.addWidget(config_panel)

        status_panel = QWidget()
        status_layout = QHBoxLayout(status_panel)
        status_layout.setContentsMargins(16, 8, 16, 8)
        self.lbl_status_dot = QLabel("●")
        self.lbl_status_dot.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14pt;")
        status_layout.addWidget(self.lbl_status_dot)
        self.lbl_status_text = QLabel("Listo para escuchar")
        self.lbl_status_text.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 9pt;")
        status_layout.addWidget(self.lbl_status_text, 1)
        main_layout.addWidget(status_panel)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.setContentsMargins(16, 2, 16, 10)
        ctrl_layout.setSpacing(8)

        self.btn_stt = QPushButton("▶ Subtítulos")
        self.btn_stt.setCursor(Qt.PointingHandCursor)
        self.btn_stt.clicked.connect(self._toggle_stt)
        self._set_btn_style(self.btn_stt, False)
        ctrl_layout.addWidget(self.btn_stt, 1)

        self.btn_ai = QPushButton("▶ Gemini AI")
        self.btn_ai.setCursor(Qt.PointingHandCursor)
        self.btn_ai.clicked.connect(self._toggle_ai)
        self._set_btn_style(self.btn_ai, False)
        ctrl_layout.addWidget(self.btn_ai, 1)
        
        self.btn_camera = QPushButton("📷")
        self.btn_camera.setFixedSize(45, 45)
        self._set_btn_style(self.btn_camera, False)
        self.btn_camera.clicked.connect(self._capture_screen)
        ctrl_layout.addWidget(self.btn_camera)
        
        self.btn_coach = QPushButton("📈 Coach")
        self.btn_coach.setFixedHeight(45)
        self._set_btn_style(self.btn_coach, False)
        self.btn_coach.clicked.connect(self._run_coach)
        ctrl_layout.addWidget(self.btn_coach)

        main_layout.addLayout(ctrl_layout)

        b2 = QFrame()
        b2.setFixedHeight(1)
        b2.setStyleSheet(f"background-color: {COLORS['border']};")
        main_layout.addWidget(b2)

        self.lbl_subtitle = QLabel("")
        self.lbl_subtitle.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(0, 0, 0, 180);
                color: {COLORS['accent_amber']};
                font-size: 14pt;
                font-weight: bold;
                padding: 12px;
                border-radius: 8px;
                border: 2px solid {COLORS['border']};
            }}
        """)
        self.lbl_subtitle.setWordWrap(True)
        self.lbl_subtitle.setAlignment(Qt.AlignCenter)
        self.lbl_subtitle.hide()
        
        sub_layout = QHBoxLayout()
        sub_layout.setContentsMargins(16, 10, 16, 0)
        sub_layout.addWidget(self.lbl_subtitle)
        main_layout.addLayout(sub_layout)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setContentsMargins(10, 10, 10, 10)
        
        self.text_area = QTextBrowser()
        self.text_area.setOpenExternalLinks(True)
        self.text_area.setStyleSheet("font-family: Consolas; font-size: 11pt; padding: 10px;")
        self.splitter.addWidget(self.text_area)

        self.code_area = QTextEdit()
        self.code_area.setReadOnly(True)
        self.code_area.setStyleSheet(f"background-color: {COLORS['title_bar']}; font-family: Consolas; font-size: 11pt; padding: 10px; color: {COLORS['accent_blue']};")
        self.splitter.addWidget(self.code_area)
        
        self.splitter.setSizes([350, 500])
        main_layout.addWidget(self.splitter, 1)

        self._show_startup_message()

    def _set_btn_style(self, btn, is_running):
        color = COLORS["accent_red"] if is_running else COLORS["accent_green"]
        bg = color
        hover = "#dc2626" if is_running else "#16a34a"
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: #051005;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
        """)

    def _populate_devices(self):
        try:
            import pyaudiowpatch as pyaudio
            pa = pyaudio.PyAudio()
            for i in range(pa.get_device_count()):
                dev = pa.get_device_info_by_index(i)
                if dev.get("maxInputChannels", 0) > 0:
                    self.device_combo.addItem(f"[{i}] {dev.get('name')}")
            pa.terminate()
        except Exception:
            pass

    def _set_status(self, msg: str, state: str = "idle"):
        self.lbl_status_text.setText(msg)
        if state == "running":
            self.lbl_status_dot.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 14pt;")
        elif state == "error":
            self.lbl_status_dot.setStyleSheet(f"color: {COLORS['accent_red']}; font-size: 14pt;")
        else:
            self.lbl_status_dot.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14pt;")

    def _run_coach(self):
        self._append_system_msg("Generando reporte de Coach. Por favor espera...")
        def run():
            from copilot.coach import generate_coach_report
            report = generate_coach_report("default_session")
            # Mostrar en hilo principal
            QTimer.singleShot(0, lambda: self._display_coach_report(report))
        threading.Thread(target=run, daemon=True).start()

    def _display_coach_report(self, report: str):
        formatted = f"""
        <div style="margin-bottom: 20px; font-family: Segoe UI, sans-serif;">
            <div style="color: {COLORS['accent_red']}; font-size: 14px; text-transform: uppercase; font-weight: bold; letter-spacing: 1px; margin-bottom: 10px;">📊 AI Coach Report</div>
            <div style="color: #ffffff; font-size: 14px; line-height: 1.5; padding: 15px; background-color: rgba(255,100,100,0.1); border-radius: 8px; border: 1px solid {COLORS['accent_red']}">
                {report.replace(chr(10), '<br>')}
            </div>
        </div>
        """
        self.text_area.append(formatted)

    def _tick_spinner(self):
        if self.is_running_ai or self.is_running_stt:
            self._spinner_idx = (self._spinner_idx + 1) % len(self.SPINNER_FRAMES)
            self.title_bar.spinner_label.setText(self.SPINNER_FRAMES[self._spinner_idx])
        else:
            self.title_bar.spinner_label.setText("")

    def _enqueue_subtitle(self, chunk: str):
        self.subtitle_queue_internal.put(chunk)
        if not self.karaoke_timer.isActive():
            self.karaoke_timer.start()

    def _process_subtitle_queue(self):
        if not self.subtitle_queue_internal.empty():
            chunk = self.subtitle_queue_internal.get()
            current_text = self.lbl_subtitle.text()
            
            words = current_text.split()
            if len(words) > 35:

                current_text = " ".join(words[-20:])
                
            new_text = f"{current_text} {chunk}".strip()
            self.lbl_subtitle.setText(new_text)
            
            if self.lbl_subtitle.isHidden():
                self.lbl_subtitle.show()
                
            self.subtitle_idle_timer.start()
        else:
            self.karaoke_timer.stop()

    def _clear_subtitle(self):
        self.lbl_subtitle.setText("")
        self.lbl_subtitle.hide()

    def _toggle_stt(self):
        if self.is_running_stt:
            self._stop_stt()
        else:
            self._start_stt()

    def _toggle_ai(self):
        if self.is_running_ai:
            self._stop_ai()
        else:
            self._start_ai()

    def _start_stt(self):
        self._ensure_audio_capture()
        self.is_running_stt = True
        self.btn_stt.setText("■ Stop Subtítulos")
        self._set_btn_style(self.btn_stt, True)
        self.spinner_timer.start(250)

        self.transcription_thread = TranscriptionWorker(
            stt_queue=self.stt_queue,
            subtitle_callback=lambda text: self.signals.stt_result.emit(text),
            error_callback=lambda err: self.signals.stt_error.emit(err)
        )
        self.transcription_thread.start()

    def _stop_stt(self):
        self.is_running_stt = False
        self.btn_stt.setText("▶ Subtítulos")
        self._set_btn_style(self.btn_stt, False)
        
        if self.transcription_thread:
            self.transcription_thread.stop()
            self.transcription_thread = None

        self._check_audio_capture_stop()

    def _start_ai(self):
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            self._show_error("No se encontró OPENROUTER_API_KEY en .env")
            return

        self._ensure_audio_capture()
        self.is_running_ai = True
        self.btn_ai.setText("■ Stop Gemini")
        self._set_btn_style(self.btn_ai, True)
        self.spinner_timer.start(250)

        self.gemini_worker = GeminiWorker(
            audio_queue=self.audio_queue,
            image_queue=self.image_queue,
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            result_callback=lambda text: self.signals.gemini_result.emit(text),
            error_callback=lambda err: self.signals.gemini_error.emit(err),
            context_content=self.context_content,
            model_name=self.model_combo.currentData(),
            get_code_state_callback=self._get_code_state_safe,
            chunk_callback=None
        )
        self.gemini_worker.start()

    def _stop_ai(self):
        self.is_running_ai = False
        self.btn_ai.setText("▶ Gemini AI")
        self._set_btn_style(self.btn_ai, False)

        if self.gemini_thread:
            self.gemini_thread.stop()
            self.gemini_thread = None
            
        self._check_audio_capture_stop()

    def _ensure_audio_capture(self):
        if self.audio_thread is not None and self.audio_thread.is_alive():
            return
            
        idx_str = self.device_combo.currentText()
        device_idx = None
        if idx_str.startswith("["):
            try:
                device_idx = int(idx_str.split("]")[0][1:])
            except ValueError:
                pass

        self.audio_thread = AudioCapture(
            ai_queue=self.audio_queue,
            stt_queue=self.stt_queue,
            device_index=device_idx,
            status_callback=lambda msg: self.signals.status_update.emit(msg, "running"),
            error_callback=lambda err: self.signals.gemini_error.emit(err)
        )
        self.audio_thread.start()

    def _check_audio_capture_stop(self):
        if not self.is_running_ai and not self.is_running_stt:
            self.spinner_timer.stop()
            self.title_bar.spinner_label.setText("")
            self._set_status("Listo", "idle")
            if self.audio_thread:
                self.audio_thread.stop()
                self.audio_thread = None

    def _capture_screen(self):
        if not self.is_running_ai:
            self._set_status("Enciende Gemini AI primero", "error")
            return
            
        try:
            from PIL import ImageGrab
            self.hide()
            QApplication.processEvents()
            time.sleep(0.1)
            
            img = ImageGrab.grab(all_screens=True)
            self.show()
            
            if self.image_queue.full():
                try:
                    self.image_queue.get_nowait()
                except queue.Empty:
                    pass
            self.image_queue.put(img)
            self._set_status("Captura enviada a Gemini", "running")
        except Exception as e:
            self.show()
            self._show_error(f"Error al capturar: {e}")

    def _display_response(self, text: str):
        self._set_status("Respuesta generada", "idle")
        
        import re
        html_body = text.replace('\n', '<br>')
        
        # Extraer [ESPAÑOL] como pregunta/contexto
        pregunta_match = re.search(r'\[ESPAÑOL\]:(.*?)(?=\[INGLÉS\]|$)', html_body, flags=re.IGNORECASE | re.DOTALL)
        pregunta_texto = pregunta_match.group(1).strip() if pregunta_match else "(Contexto deducido)"
        html_body = re.sub(r'\[ESPAÑOL\]:.*?(?=\[INGLÉS\]|$)', '', html_body, flags=re.IGNORECASE | re.DOTALL)
        
        # Extraer [INGLÉS] como respuesta sugerida
        html_body = re.sub(r'\[INGLÉS\]:', '', html_body, flags=re.IGNORECASE)

        formatted = f"""
        <div style="margin-bottom: 20px; font-family: Segoe UI, sans-serif;">
            <div style="color: {COLORS['accent_blue']}; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Question / Context</div>
            <div style="color: {COLORS['text_dim']}; font-size: 13px; margin-bottom: 12px; padding-left: 10px; border-left: 2px solid {COLORS['accent_blue']};">
                <i>{pregunta_texto}</i>
            </div>
            
            <div style="color: {COLORS['accent_green']}; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">Suggested Answer</div>
            <div style="color: #ffffff; font-size: 15px; line-height: 1.5; padding: 12px; background-color: rgba(255,255,255,0.05); border-radius: 8px;">
                {html_body}
            </div>
        </div>
        <hr style="border: 0; height: 1px; background-color: {COLORS['border']}; margin: 20px 0;">
        """
        self.text_area.append(formatted)
        
        scrollbar = self.text_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _show_error(self, err_msg: str):
        self._set_status("Error", "error")
        html = f'<div style="color: {COLORS["accent_red"]}; margin-bottom: 15px;">❌ <b>Error:</b> {err_msg}</div>'
        self.text_area.append(html)

    def _show_startup_message(self):
        selected_model = self.model_combo.currentData()
        msg = f"""
        <div style="color: {COLORS['accent_blue']};">
            <b>Interview Copilot (PySide6 Overlay)</b><br>
            Proveedor: OPENROUTER<br>
            Modelo seleccionado: {selected_model}<br><br>
            <i>Atajo Global: Presiona <b>Ctrl+Shift+H</b> para ocultar/mostrar.</i>
        </div>
        """
        if "WARNING" in self.context_content:
            msg += f"<div style='color: {COLORS['accent_red']};'><br>{self.context_content}</div>"
        
        self.text_area.setHtml(msg)

    def _on_toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def closeEvent(self, event):
        if self.is_running_ai:
            self._stop_ai()
        if self.is_running_stt:
            self._stop_stt()
        event.accept()

def run_app():
    # Permite que la aplicación PySide6 se cierre correctamente si presionas Ctrl+C en la terminal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    window = CopilotApp()
    window.show()
    sys.exit(app.exec())
