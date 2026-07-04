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
    "text_dim":     "#94a3b8",
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
