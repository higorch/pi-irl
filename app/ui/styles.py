"""Estilo limpo e linear do Pi-IRL."""

APP_STYLESHEET = """
QWidget {
    color: #e8ecf2;
    font-family: "Segoe UI", "Ubuntu", "Noto Sans", sans-serif;
    font-size: 13px;
}

QMainWindow, QWidget#rootArea, QWidget#scrollContent {
    background-color: #0e1013;
}

QScrollArea#configScroll {
    background: transparent;
    border: none;
}

QWidget#tabPage {
    background: transparent;
}

QLabel#brandLabel {
    font-size: 26px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 0.3px;
    margin: 0;
    padding: 0;
}

QLabel#subtitleLabel {
    font-size: 12px;
    color: #8b93a3;
    margin: 0;
    padding: 0;
}

QFrame#card {
    background-color: #16191e;
    border: 1px solid #242933;
    border-radius: 14px;
}

QLabel#sectionTitle {
    font-size: 11px;
    font-weight: 700;
    color: #7a8496;
    letter-spacing: 1.1px;
    text-transform: uppercase;
    margin: 0 0 4px 0;
    padding: 0;
}

QLabel#fieldLabel {
    font-size: 12px;
    font-weight: 600;
    color: #a8b0bf;
    margin: 0;
    padding: 0;
}

QLabel#infoValue {
    background-color: #0c0e12;
    border: 1px solid #2a303a;
    border-radius: 10px;
    padding: 10px 12px;
    color: #9aa3b5;
    font-weight: 600;
}

QFrame#depsCard {
    background-color: #16191e;
    border: 1px solid #242933;
    border-radius: 12px;
}

QWidget#tabsWrap, QWidget#tabRow, QWidget#tabPage, QStackedWidget#tabStack {
    background: transparent;
    border: none;
}

QFrame#tabPanel {
    background-color: #12151a;
    border: 1px solid #242933;
    border-radius: 14px;
}

QPushButton#tabButton {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    color: #8b93a3;
    font-weight: 700;
    font-size: 12px;
    padding: 8px 0 10px 0;
    margin: 0;
    text-align: left;
}

QPushButton#tabButton:checked {
    color: #ffffff;
    border-bottom: 2px solid #3dd68c;
    background: transparent;
}

QPushButton#tabButton:hover:!checked {
    color: #d5dae6;
    background: transparent;
}

QLabel#depsTitle {
    font-size: 11px;
    font-weight: 700;
    color: #7a8496;
    letter-spacing: 0.9px;
    text-transform: uppercase;
}

QLabel#depsChipOk, QLabel#depsChipError {
    border-radius: 999px;
    padding: 5px 8px;
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
    color: #8b93a3;
    border: 1px solid #2a303a;
    border-radius: 14px;
    font-size: 12px;
    font-weight: 700;
    padding: 0 12px;
}

QPushButton#depsRecheckButton:hover {
    color: #ffffff;
    border: 1px solid #3dd68c;
}

QLabel#rtspValue {
    background-color: #0c0e12;
    border: 1px solid #2a303a;
    border-radius: 10px;
    padding: 10px 12px;
    color: #3dd68c;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    font-weight: 600;
}

QLabel#rtspHint {
    font-size: 11px;
    color: #8b93a3;
    line-height: 1.35;
}

QLabel#alertWarning, QLabel#alertOk {
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 12px;
    font-weight: 600;
}

QLabel#alertWarning {
    color: #f5c451;
    background-color: rgba(245, 196, 81, 0.08);
    border: 1px solid rgba(245, 196, 81, 0.28);
    border-left: 3px solid #f5c451;
}

QLabel#alertOk {
    color: #3dd68c;
    background-color: rgba(61, 214, 140, 0.08);
    border: 1px solid rgba(61, 214, 140, 0.22);
    border-left: 3px solid #3dd68c;
}

QFrame#netRow {
    background-color: #0c0e12;
    border: 1px solid #2a303a;
    border-radius: 10px;
}

QLabel#netName {
    font-size: 13px;
    font-weight: 700;
    color: #f3f5f8;
}

QLabel#netMeta {
    font-size: 11px;
    color: #8b93a3;
}

QLabel#netIp {
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    font-weight: 600;
    color: #d5dae6;
}

QLabel#netChipWarn {
    border-radius: 999px;
    padding: 5px 8px;
    font-size: 12px;
    font-weight: 600;
    color: #f5c451;
    background-color: rgba(245, 196, 81, 0.08);
    border: 1px solid rgba(245, 196, 81, 0.28);
}

QPushButton#copyButton {
    background-color: #1e232b;
    color: #d5dae6;
    border: 1px solid #333a46;
    border-radius: 10px;
    padding: 0 16px;
    font-weight: 700;
    font-size: 12px;
    min-width: 88px;
}

QPushButton#copyButton:hover {
    border: 1px solid #3dd68c;
    color: #ffffff;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #0c0e12;
    border: 1px solid #2a303a;
    border-radius: 10px;
    padding: 0 12px;
    min-height: 40px;
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

/* Estilo windows11 do Qt exige fonte do combo em pt (px gera "Point size <= 0"). */
QComboBox {
    padding-right: 30px;
    font-size: 10pt;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
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
    padding: 12px 20px;
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
    background-color: #1e232b;
    color: #f2f4f8;
    border: 1px solid #333a46;
    border-radius: 12px;
    padding: 12px 20px;
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
    background-color: #1e232b;
    color: #d5dae6;
    border: 1px solid #333a46;
    border-radius: 10px;
    padding: 0 14px;
    font-weight: 700;
    font-size: 12px;
    min-width: 96px;
}

QPushButton#refreshButton:hover {
    border: 1px solid #3dd68c;
    color: #ffffff;
}

QLabel#statusBadge {
    background-color: #1e232b;
    border: 1px solid #333a46;
    border-radius: 18px;
    padding: 0 14px;
    font-size: 12px;
    font-weight: 800;
}

QPlainTextEdit#logView {
    background-color: #0a0c0f;
    border: 1px solid #242933;
    border-radius: 12px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    color: #b7c0d0;
    padding: 12px;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 1px;
}

QScrollBar::handle:vertical {
    background: #333a46;
    border-radius: 4px;
    min-height: 28px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""

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
    letter-spacing: 0.6px;
}

QLabel#fieldLabel {
    font-size: 10px;
}

QLineEdit, QComboBox, QSpinBox, QLabel#infoValue, QLabel#rtspValue {
    border-radius: 8px;
    padding: 0 8px;
    min-height: 32px;
    font-size: 11px;
}

QComboBox {
    padding-right: 22px;
    font-size: 8pt;
}

QComboBox::drop-down {
    width: 20px;
}

QFrame#tabPanel {
    border-radius: 10px;
}

QPushButton#tabButton {
    font-size: 10px;
    padding: 6px 0 8px 0;
}

QPushButton#startButton, QPushButton#stopButton {
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
}

QPushButton#refreshButton, QPushButton#copyButton {
    border-radius: 8px;
    padding: 0 8px;
    font-size: 10px;
    min-width: 72px;
}

QPlainTextEdit#logView {
    border-radius: 8px;
    font-size: 10px;
    padding: 8px;
}

QFrame#depsCard {
    border-radius: 8px;
}

QLabel#depsTitle {
    font-size: 9px;
}

QPushButton#depsRecheckButton {
    font-size: 10px;
    padding: 0 8px;
}

QLabel#depsChipOk, QLabel#depsChipError, QLabel#netChipWarn {
    font-size: 10px;
    padding: 3px 6px;
}

QLabel#depsPorts, QLabel#rtspHint, QLabel#netMeta {
    font-size: 9px;
}

QLabel#alertWarning, QLabel#alertOk {
    border-radius: 8px;
    padding: 6px 8px;
    font-size: 10px;
}

QFrame#netRow {
    border-radius: 8px;
}

QLabel#netName, QLabel#netIp {
    font-size: 11px;
}
"""
