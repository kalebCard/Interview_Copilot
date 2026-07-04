import sys
import os
import signal
import queue
import re
import ctypes
import keyboard

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTextBrowser, QFrame, QSplitter, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, QObject, Signal

from copilot.core.logger import get_logger
from copilot.ui.theme import COLORS, MAIN_STYLE
from copilot.ui.title_bar import TitleBar
from copilot.core.app_controller import AppController

logger = get_logger(__name__)

class WorkerSignals(QObject):
    toggle_visibility = Signal()
    display_response = Signal(str)
    show_error = Signal(str)
    status_update = Signal(str, str)
    enqueue_subtitle = Signal(str)

class CopilotApp(QMainWindow):
    SPINNER_FRAMES = ["● ○ ○", "○ ● ○", "○ ○ ●", "○ ● ○"]

    def __init__(self):
        super().__init__()

        self._spinner_idx = 0
        
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self._tick_spinner)

        self.signals = WorkerSignals()
        self.signals.toggle_visibility.connect(self._on_toggle_visibility)
        self.signals.display_response.connect(self._display_response)
        self.signals.show_error.connect(self._show_error)
        self.signals.status_update.connect(self._set_status)
        self.signals.enqueue_subtitle.connect(self._enqueue_subtitle)

        # App Controller takes care of business logic
        self.controller = AppController(
            gemini_result_cb=lambda text: self.signals.display_response.emit(text),
            gemini_error_cb=lambda err: self.signals.show_error.emit(err),
            stt_result_cb=lambda text: self.signals.enqueue_subtitle.emit(text),
            stt_error_cb=lambda err: self.signals.show_error.emit(err),
            status_update_cb=lambda msg, state: self.signals.status_update.emit(msg, state)
        )

        self.subtitle_queue_internal = queue.Queue()
        self.karaoke_timer = QTimer(self)
        self.karaoke_timer.setInterval(80)
        self.karaoke_timer.timeout.connect(self._process_subtitle_queue)
        
        self.subtitle_idle_timer = QTimer(self)
        self.subtitle_idle_timer.setInterval(3000)
        self.subtitle_idle_timer.setSingleShot(True)
        self.subtitle_idle_timer.timeout.connect(self._clear_subtitle)

        try:
            keyboard.add_hotkey('ctrl+shift+h', lambda: self.signals.toggle_visibility.emit())
        except Exception as e:
            logger.warning(f"No se pudo registrar atajo global: {e}")

        self._configure_window()
        self._build_ui()

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


    def _set_status(self, msg: str, state: str = "idle"):
        self.lbl_status_text.setText(msg)
        if state == "running":
            self.lbl_status_dot.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 14pt;")
        elif state == "error":
            self.lbl_status_dot.setStyleSheet(f"color: {COLORS['accent_red']}; font-size: 14pt;")
        else:
            self.lbl_status_dot.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14pt;")
            if not self.controller.is_running_ai and not self.controller.is_running_stt:
                self.spinner_timer.stop()
                self.title_bar.spinner_label.setText("")

    def _run_coach(self):
        self._append_system_msg("Generando reporte de Coach. Por favor espera...")
        def display_report(report: str):
            QTimer.singleShot(0, lambda: self._display_coach_report(report))
        self.controller.run_coach(display_report)

    def _append_system_msg(self, msg: str):
        self.text_area.append(f"<div style='color: {COLORS['accent_blue']}; margin-bottom: 15px;'>ℹ️ {msg}</div>")

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
        if self.controller.is_running_ai or self.controller.is_running_stt:
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
        if self.controller.is_running_stt:
            self.controller.stop_stt()
            self.btn_stt.setText("▶ Subtítulos")
            self._set_btn_style(self.btn_stt, False)
        else:
            self.controller.start_stt(None)
            self.btn_stt.setText("■ Stop Subtítulos")
            self._set_btn_style(self.btn_stt, True)
            self.spinner_timer.start(250)

    def _toggle_ai(self):
        if self.controller.is_running_ai:
            self.controller.stop_ai()
            self.btn_ai.setText("▶ Gemini AI")
            self._set_btn_style(self.btn_ai, False)
        else:
            api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
            self.controller.start_ai(api_key, self.model_combo.currentData(), None)
            if self.controller.is_running_ai:
                self.btn_ai.setText("■ Stop Gemini")
                self._set_btn_style(self.btn_ai, True)
                self.spinner_timer.start(250)

    def _capture_screen(self):
        self.hide()
        QApplication.processEvents()
        QTimer.singleShot(100, self._do_capture_and_show)

    def _do_capture_and_show(self):
        self.controller.capture_screen()
        self.show()

    def _display_response(self, text: str):
        self._set_status("Respuesta generada", "idle")
        
        # Extract code blocks [CÓDIGO]...[/CÓDIGO] before HTML conversion
        code_match = re.search(r'\[CÓDIGO\](.*?)\[/CÓDIGO\]', text, flags=re.DOTALL)
        if code_match:
            code_content = code_match.group(1).strip()
            self.code_area.setPlainText(code_content)
            self.controller.set_code_state_safe(code_content)
            # Remove the code block from the display text
            text = re.sub(r'\[CÓDIGO\].*?\[/CÓDIGO\]', '', text, flags=re.DOTALL).strip()
        
        html_body = text.replace('\n', '<br>')
        
        pregunta_match = re.search(r'\[ESPAÑOL\]:(.*?)(?=\[INGLÉS\]|$)', html_body, flags=re.IGNORECASE | re.DOTALL)
        pregunta_texto = pregunta_match.group(1).strip() if pregunta_match else "(Contexto deducido)"
        html_body = re.sub(r'\[ESPAÑOL\]:.*?(?=\[INGLÉS\]|$)', '', html_body, flags=re.IGNORECASE | re.DOTALL)
        
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
        if "WARNING" in self.controller.context_content:
            msg += f"<div style='color: {COLORS['accent_red']};'><br>{self.controller.context_content}</div>"
        
        self.text_area.setHtml(msg)

    def _on_toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def closeEvent(self, event):
        self.controller.stop_all()
        event.accept()

def run_app():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    window = CopilotApp()
    window.show()
    sys.exit(app.exec())
