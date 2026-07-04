from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from copilot.ui.theme import COLORS

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
