"""Estilo limpo e espaçado do Pi-IRL."""

APP_STYLESHEET = """
/* Cor de texto e fonte globais; o fundo fica só nos containers nomeados
   para que os widgets internos não pintem por cima dos cards. */
QWidget {
    color: #eceff4;
    font-family: "Segoe UI", "Ubuntu", "Noto Sans", sans-serif;
    font-size: 13px;
}

QMainWindow, QWidget#rootArea, QWidget#scrollContent {
    background-color: #101214;
}

QScrollArea#configScroll {
    background: transparent;
    border: none;
}

QLabel#brandLabel {
    font-size: 28px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 0.4px;
    margin: 0;
    padding: 0;
}

QLabel#subtitleLabel {
    font-size: 13px;
    color: #8f98a8;
    margin: 0;
    padding: 0;
}

QFrame#card {
    background-color: #171a1f;
    border: 1px solid #252a33;
    border-radius: 16px;
}

QLabel#sectionTitle {
    font-size: 12px;
    font-weight: 700;
    color: #8f98a8;
    letter-spacing: 0.8px;
    margin: 0;
    padding: 0;
}

QLabel#fieldLabel {
    font-size: 12px;
    font-weight: 600;
    color: #b4bcc8;
    margin: 0;
    padding: 0;
}

QLabel#infoValue {
    background-color: #0d0f12;
    border: 1px solid #2a303a;
    border-radius: 10px;
    padding: 8px 12px;
    color: #9aa3b5;
    font-weight: 600;
}

QFrame#depsCard {
    background-color: transparent;
    border: 1px solid #252a33;
    border-radius: 12px;
}

QLabel#depsTitle {
    font-size: 11px;
    font-weight: 700;
    color: #7d879c;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}

QLabel#depsChipOk, QLabel#depsChipError {
    border-radius: 999px;
    padding: 4px 2px;
    font-size: 12px;
    font-weight: 600;
}

QLabel#depsChipOk {
    color: #3dd68c;
    background-color: rgba(61, 214, 140, 0.08);
    border: 1px solid rgba(61, 214, 140, 0.22);
}

QLabel#depsChipError {
    color: #ff7b7b;
    background-color: rgba(255, 107, 107, 0.08);
    border: 1px solid rgba(255, 107, 107, 0.25);
}

QLabel#depsPorts {
    font-size: 11px;
    color: #6d7685;
    padding-top: 2px;
}

QPushButton#depsRecheckButton {
    background-color: transparent;
    color: #8f98a8;
    border: 1px solid #2a303a;
    border-radius: 14px;
    font-size: 14px;
    font-weight: 700;
    padding: 0;
}

QPushButton#depsRecheckButton:hover {
    color: #ffffff;
    border: 1px solid #3dd68c;
}

QLabel#rtspValue {
    background-color: #0d0f12;
    border: 1px solid #2a303a;
    border-radius: 10px;
    padding: 8px 12px;
    color: #3dd68c;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    font-weight: 600;
}

QLabel#rtspHint {
    font-size: 11px;
    color: #8f98a8;
}

QPushButton#copyButton {
    background-color: #22272f;
    color: #d5dae6;
    border: 1px solid #333a46;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 700;
    font-size: 12px;
}

QPushButton#copyButton:hover {
    border: 1px solid #3dd68c;
    color: #ffffff;
}


QLineEdit, QComboBox, QSpinBox {
    background-color: #0d0f12;
    border: 1px solid #2a303a;
    border-radius: 10px;
    padding: 8px 12px;
    min-height: 22px;
    color: #f3f5f8;
    selection-background-color: #1f7a4d;
}

QLineEdit:hover, QComboBox:hover, QSpinBox:hover {
    border: 1px solid #3a4250;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #3dd68c;
}

QLineEdit::placeholder {
    color: #6d7685;
}

QComboBox {
    padding-right: 30px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 26px;
    border: none;
    background: transparent;
}

QComboBox QAbstractItemView {
    background-color: #171a1f;
    border: 1px solid #2a303a;
    border-radius: 8px;
    padding: 6px;
    outline: 0;
    selection-background-color: #1f7a4d;
    selection-color: #ffffff;
}

QSpinBox::up-button, QSpinBox::down-button {
    width: 18px;
    border: none;
    background: transparent;
}

QPushButton#startButton {
    background-color: #1f9a57;
    color: #ffffff;
    border: none;
    border-radius: 12px;
    padding: 14px 24px;
    font-weight: 800;
    font-size: 14px;
}

QPushButton#startButton:hover {
    background-color: #24b366;
}

QPushButton#startButton:disabled {
    background-color: #1b2a22;
    color: #5f7267;
}

QPushButton#stopButton {
    background-color: #22272f;
    color: #f2f4f8;
    border: 1px solid #333a46;
    border-radius: 12px;
    padding: 14px 24px;
    font-weight: 800;
    font-size: 14px;
}

QPushButton#stopButton:hover {
    background-color: #9b2f2f;
    border: 1px solid #9b2f2f;
}

QPushButton#stopButton:disabled {
    background-color: #181b20;
    color: #5a6270;
    border: 1px solid #252a33;
}

QPushButton#refreshButton {
    background-color: #22272f;
    color: #d5dae6;
    border: 1px solid #333a46;
    border-radius: 10px;
    padding: 10px 14px;
    font-weight: 700;
    font-size: 12px;
}

QPushButton#refreshButton:hover {
    border: 1px solid #3dd68c;
    color: #ffffff;
}

QLabel#statusBadge {
    background-color: #22272f;
    border: 1px solid #333a46;
    border-radius: 20px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 800;
}

QPlainTextEdit#logView {
    background-color: #0b0d10;
    border: 1px solid #252a33;
    border-radius: 12px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    color: #b7c0d0;
    padding: 12px;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 2px;
}

QScrollBar::handle:vertical {
    background: #333a46;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""

# Ajustes para telas pequenas (~3.5", 480x320 etc.)
COMPACT_STYLESHEET = """
QWidget {
    font-size: 11px;
}

QLabel#brandLabel {
    font-size: 18px;
}

QLabel#subtitleLabel {
    font-size: 10px;
}

QFrame#card {
    border-radius: 10px;
}

QLabel#sectionTitle {
    font-size: 10px;
    letter-spacing: 0.4px;
}

QLabel#fieldLabel {
    font-size: 10px;
}

QLineEdit, QComboBox, QSpinBox, QLabel#infoValue {
    border-radius: 8px;
    padding: 5px 8px;
    min-height: 18px;
    font-size: 11px;
}

QComboBox {
    padding-right: 22px;
}

QComboBox::drop-down {
    width: 20px;
}

QPushButton#startButton, QPushButton#stopButton {
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
}

QPushButton#refreshButton {
    border-radius: 8px;
    padding: 6px 8px;
    font-size: 10px;
}

QPlainTextEdit#logView {
    border-radius: 8px;
    font-size: 10px;
    padding: 6px;
}

QScrollBar:vertical {
    width: 8px;
}

QFrame#depsCard {
    border-radius: 8px;
}

QLabel#depsTitle {
    font-size: 9px;
}

QLabel#depsChipOk, QLabel#depsChipError {
    font-size: 10px;
    padding: 3px 1px;
}

QLabel#depsPorts {
    font-size: 9px;
}

QPushButton#depsRecheckButton {
    border-radius: 12px;
    font-size: 12px;
}

QLabel#rtspValue {
    font-size: 10px;
    border-radius: 8px;
    padding: 5px 8px;
}

QPushButton#copyButton {
    border-radius: 8px;
    padding: 6px 8px;
    font-size: 10px;
}
"""
