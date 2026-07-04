import keyboard
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTabWidget, QWidget, QFormLayout, QLineEdit, QDoubleSpinBox, QSpinBox
)
from PySide6.QtCore import Qt
from copilot.ui.theme import COLORS
from copilot.core import settings

class HotkeyLineEdit(QLineEdit):
    def __init__(self, default_key="", parent=None):
        super().__init__(parent)
        self.setText(default_key)
        self.setReadOnly(True)
        self.setStyleSheet(f"background-color: {COLORS['surface']}; color: {COLORS['text_dim']}; border: 1px solid {COLORS['border']}; border-radius: 4px; padding: 4px;")

    def keyPressEvent(self, event):
        # Prevent default behavior to avoid typing in the box
        key_name = self.get_key_name(event)
        if key_name:
            self.setText(key_name)
    
    def get_key_name(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        # Don't register just a modifier
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return None
            
        parts = []
        if modifiers & Qt.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.AltModifier:
            parts.append("alt")
            
        key_str = ""
        # Handle some special keys or fallback to text
        if Qt.Key_A <= key <= Qt.Key_Z:
            key_str = chr(key).lower()
        elif Qt.Key_0 <= key <= Qt.Key_9:
            key_str = chr(key)
        elif key == Qt.Key_F1: key_str = "f1"
        elif key == Qt.Key_F2: key_str = "f2"
        elif key == Qt.Key_F3: key_str = "f3"
        elif key == Qt.Key_F4: key_str = "f4"
        elif key == Qt.Key_F5: key_str = "f5"
        elif key == Qt.Key_F6: key_str = "f6"
        elif key == Qt.Key_F7: key_str = "f7"
        elif key == Qt.Key_F8: key_str = "f8"
        elif key == Qt.Key_F9: key_str = "f9"
        elif key == Qt.Key_F10: key_str = "f10"
        elif key == Qt.Key_F11: key_str = "f11"
        elif key == Qt.Key_F12: key_str = "f12"
        else:
            try:
                key_str = chr(key).lower()
            except:
                return None
                
        if not key_str:
            return None
            
        parts.append(key_str)
        return "+".join(parts)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración - Interview Copilot")
        self.resize(450, 400)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS['bg']}; color: {COLORS['text']}; }}
            QLabel {{ color: {COLORS['text']}; }}
            QTabWidget::pane {{ border: 1px solid {COLORS['border']}; background-color: {COLORS['surface']}; }}
            QTabBar::tab {{ background-color: {COLORS['surface']}; color: {COLORS['text_dim']}; padding: 8px 16px; border: 1px solid {COLORS['border']}; }}
            QTabBar::tab:selected {{ background-color: {COLORS['accent_blue']}; color: #ffffff; }}
        """)

        # Load current settings
        self.current_settings = settings.load_settings()

        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self._setup_general_tab()
        self._setup_hotkeys_tab()
        self._setup_audio_tab()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setStyleSheet(f"background-color: {COLORS['surface']}; color: {COLORS['text']}; padding: 6px 16px; border-radius: 4px;")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_save = QPushButton("Guardar")
        self.btn_save.setStyleSheet(f"background-color: {COLORS['accent_blue']}; color: #ffffff; padding: 6px 16px; border-radius: 4px; font-weight: bold;")
        self.btn_save.clicked.connect(self._save_and_close)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        main_layout.addLayout(btn_layout)

    def _setup_general_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.model_combo = QComboBox()
        self.model_combo.setStyleSheet(f"background-color: {COLORS['surface']}; color: {COLORS['text']}; padding: 4px; border: 1px solid {COLORS['border']}; border-radius: 4px;")
        
        current_model = self.current_settings.get("model", settings.DEFAULTS["model"])
        idx = 0
        for i, (name, val) in enumerate(settings.MODELS):
            self.model_combo.addItem(name, val)
            if val == current_model:
                idx = i
        self.model_combo.setCurrentIndex(idx)
        
        layout.addRow("Modelo IA:", self.model_combo)
        self.tabs.addTab(tab, "General")

    def _setup_hotkeys_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.hk_visibility = HotkeyLineEdit(self.current_settings.get("hotkey_toggle_visibility", settings.DEFAULTS["hotkey_toggle_visibility"]))
        self.hk_ai = HotkeyLineEdit(self.current_settings.get("hotkey_toggle_ai", settings.DEFAULTS["hotkey_toggle_ai"]))
        self.hk_stt = HotkeyLineEdit(self.current_settings.get("hotkey_toggle_stt", settings.DEFAULTS["hotkey_toggle_stt"]))
        self.hk_screen = HotkeyLineEdit(self.current_settings.get("hotkey_capture_screen", settings.DEFAULTS["hotkey_capture_screen"]))

        layout.addRow("Ocultar/Mostrar UI:", self.hk_visibility)
        layout.addRow("Play/Stop AI:", self.hk_ai)
        layout.addRow("Play/Stop STT:", self.hk_stt)
        layout.addRow("Capturar Pantalla:", self.hk_screen)
        
        lbl_hint = QLabel("<i>Haz clic en la caja y presiona la combinación de teclas.</i>")
        lbl_hint.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        layout.addRow("", lbl_hint)

        self.tabs.addTab(tab, "Atajos")

    def _setup_audio_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        style = f"background-color: {COLORS['surface']}; color: {COLORS['text']}; border: 1px solid {COLORS['border']}; padding: 4px;"

        self.spin_silence = QSpinBox()
        self.spin_silence.setRange(100, 5000)
        self.spin_silence.setSingleStep(100)
        self.spin_silence.setValue(self.current_settings.get("silence_threshold", settings.DEFAULTS["silence_threshold"]))
        self.spin_silence.setStyleSheet(style)

        self.spin_max_dur = QDoubleSpinBox()
        self.spin_max_dur.setRange(2.0, 30.0)
        self.spin_max_dur.setSingleStep(1.0)
        self.spin_max_dur.setValue(self.current_settings.get("vad_max_duration", settings.DEFAULTS["vad_max_duration"]))
        self.spin_max_dur.setStyleSheet(style)

        self.spin_timeout = QDoubleSpinBox()
        self.spin_timeout.setRange(0.5, 5.0)
        self.spin_timeout.setSingleStep(0.1)
        self.spin_timeout.setValue(self.current_settings.get("vad_silence_timeout", settings.DEFAULTS["vad_silence_timeout"]))
        self.spin_timeout.setStyleSheet(style)

        layout.addRow("Umbral Silencio (RMS):", self.spin_silence)
        layout.addRow("Duración Máxima Chunk (s):", self.spin_max_dur)
        layout.addRow("Timeout Silencio (s):", self.spin_timeout)

        self.tabs.addTab(tab, "Audio/VAD")

    def _save_and_close(self):
        new_settings = {
            "model": self.model_combo.currentData(),
            "hotkey_toggle_visibility": self.hk_visibility.text(),
            "hotkey_toggle_ai": self.hk_ai.text(),
            "hotkey_toggle_stt": self.hk_stt.text(),
            "hotkey_capture_screen": self.hk_screen.text(),
            "silence_threshold": self.spin_silence.value(),
            "vad_max_duration": self.spin_max_dur.value(),
            "vad_silence_timeout": self.spin_timeout.value(),
        }
        settings.save_settings(new_settings)
        self.accept()
