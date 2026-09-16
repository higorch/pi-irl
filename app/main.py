"""Ponto de entrada do Pi-IRL."""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que o pacote `app` seja encontrado ao executar python app/main.py
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Pi-IRL")
    app.setOrganizationName("Pi-IRL")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
