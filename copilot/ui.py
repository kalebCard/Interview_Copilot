
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
    GEMINI_MODEL,
    load_resume,
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

        lbl_model = QLabel(GEMINI_MODEL)
        lbl_model.setStyleSheet(f"color: {COLORS['text_muted']}; font-family: Consolas; font-size: 9pt;")
        layout.addWidget(lbl_model)

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

        self.resume_content = load_resume()
        self.system_prompt = build_system_prompt(self.resume_content)

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

    def _get_code_state_safe(self):
        with self.code_state_lock:
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
        
        self.btn_capture = QPushButton("📷")
        self.btn_capture.setCursor(Qt.PointingHandCursor)
        self.btn_capture.clicked.connect(self._capture_screen)
        self.btn_capture.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface2']};
                color: {COLORS['text']};
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-size: 12pt;
            }}
            QPushButton:hover {{ background-color: {COLORS['border']}; }}
        """)
        ctrl_layout.addWidget(self.btn_capture)

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

        self.gemini_thread = GeminiWorker(
            audio_queue=self.audio_queue,
            image_queue=self.image_queue,
            api_key=api_key,
            result_callback=lambda text: self.signals.gemini_result.emit(text),
            error_callback=lambda err: self.signals.gemini_error.emit(err),
            system_prompt=self.system_prompt,
            get_code_state_callback=lambda: self._get_code_state_safe()
        )
        self.gemini_thread.start()

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
        self._set_status("Respuesta generada", "running")
        
        formatted = text
        
        # Extraer bloque de código si existe
        code_match = re.search(r"\[CÓDIGO\](.*?)\[/CÓDIGO\]", formatted, flags=re.DOTALL | re.IGNORECASE)
        if code_match:
            new_code = code_match.group(1).strip()
            self._set_code_state_safe(new_code)
            self.code_area.setPlainText(new_code)
            # Reemplazar con un pequeño aviso visual en el chat
            formatted = re.sub(
                r"\[CÓDIGO\].*?\[/CÓDIGO\]", 
                f'<div style="color: {COLORS["accent_blue"]};">[💻 Código actualizado en el panel derecho]</div>', 
                formatted, 
                flags=re.DOTALL | re.IGNORECASE
            )
        formatted = re.sub(
            r"\[ESPAÑOL\](.*?)\[INGLÉS\](.*)",
            f'<div style="color: {COLORS["accent_amber"]}; margin-bottom: 8px;"><b>[ESPAÑOL]</b>\\1</div><div style="color: {COLORS["accent_blue"]};"><b>[INGLÉS]</b>\\2</div>',
            formatted, flags=re.DOTALL
        )
        
        formatted = formatted.replace('\n', '<br>')
        formatted = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', formatted)
        formatted = re.sub(r'\*(.*?)\*', r'<i>\1</i>', formatted)
        
        formatted = re.sub(r'```(.*?)```', r'<pre style="background-color: #22273a; padding: 5px;">\1</pre>', formatted, flags=re.DOTALL)
        
        html = f'<div style="margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid {COLORS["border"]};">{formatted}</div>'
        self.text_area.append(html)
        
        scrollbar = self.text_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _show_error(self, err_msg: str):
        self._set_status("Error", "error")
        html = f'<div style="color: {COLORS["accent_red"]}; margin-bottom: 15px;">❌ <b>Error:</b> {err_msg}</div>'
        self.text_area.append(html)

    def _show_startup_message(self):
        msg = f"""
        <div style="color: {COLORS['accent_blue']};">
            <b>Interview Copilot (PySide6 Overlay)</b><br>
            Proveedor: OPENROUTER<br>
            Modelo: {GEMINI_MODEL}<br><br>
            <i>Atajo Global: Presiona <b>Ctrl+Shift+H</b> para ocultar/mostrar.</i>
        </div>
        """
        if "WARNING" in self.resume_content:
            msg += f"<div style='color: {COLORS['accent_red']};'><br>{self.resume_content}</div>"
        
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
