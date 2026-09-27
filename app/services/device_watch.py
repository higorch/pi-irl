"""Detecta câmeras e microfones USB conectados/removidos sem varredura pesada.

Linux/Pi: inotify em /dev e /dev/snd (QFileSystemWatcher) + assinatura barata
(nomes /dev/video* e nós de captura ALSA). Windows: sinais do QMediaDevices.
"""

from __future__ import annotations

import os
import platform

from PySide6.QtCore import QFileSystemWatcher, QLoggingCategory, QObject, QTimer, Signal

# udev cria o nó antes de terminar de configurar o dispositivo
SETTLE_MS = 1500
FALLBACK_POLL_MS = 10000


def _linux_signature() -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        video = tuple(sorted(n for n in os.listdir("/dev") if n.startswith("video")))
    except OSError:
        video = ()
    try:
        audio = tuple(
            sorted(n for n in os.listdir("/dev/snd") if n.startswith("pcmC") and n.endswith("c"))
        )
    except OSError:
        audio = ()
    return video, audio


class DeviceWatcher(QObject):
    """Emite `changed` quando o conjunto de câmeras/microfones muda."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(SETTLE_MS)
        self._settle.timeout.connect(self._check)
        self._signature: object = None
        self._media = None

        if platform.system() == "Linux":
            self._watcher = QFileSystemWatcher(self)
            self._watcher.directoryChanged.connect(self._schedule)
            self._watch_linux_dirs()
            self._signature = _linux_signature()
            self._poll = QTimer(self)
            self._poll.setInterval(FALLBACK_POLL_MS)
            self._poll.timeout.connect(self._check)
            self._poll.start()
        else:
            self._init_media_devices()

    def _watch_linux_dirs(self) -> None:
        watched = set(self._watcher.directories())
        for path in ("/dev", "/dev/snd"):
            if path not in watched and os.path.isdir(path):
                self._watcher.addPath(path)

    def _init_media_devices(self) -> None:
        QLoggingCategory.setFilterRules("qt.multimedia.ffmpeg=false")
        try:
            from PySide6.QtMultimedia import QMediaDevices
        except ImportError:
            return
        self._media = QMediaDevices(self)
        self._media.videoInputsChanged.connect(self._schedule)
        self._media.audioInputsChanged.connect(self._schedule)

    def _schedule(self, *_args: object) -> None:
        self._settle.start()

    def _check(self) -> None:
        if self._media is not None:
            self.changed.emit()
            return
        self._watch_linux_dirs()
        signature = _linux_signature()
        if signature != self._signature:
            self._signature = signature
            self.changed.emit()
