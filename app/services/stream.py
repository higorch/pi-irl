"""Orquestração da transmissão IRL (+ bonding opcional)."""

from __future__ import annotations

import re
import time

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from app.models.stream_config import StreamConfig, StreamStatus
from app.services import bonding as bonding_service
from app.services.ffmpeg import FFmpegService
from app.services.system_health import power_warnings

_FRAME_RE = re.compile(r"frame=\s*(\d+)")
# Sem quadro novo por esse tempo = câmera travada (1º quadro tem mais folga para abrir a câmera)
STALL_TIMEOUT_S = 10.0
STALL_FIRST_FRAME_S = 25.0


class StreamService(QObject):
    """Coordena status, validação, bonding opcional e FFmpeg."""

    status_changed = Signal(str)
    log_line = Signal(str)
    validation_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._status = StreamStatus.OFFLINE
        self._ffmpeg = FFmpegService(self)
        self._bonding = bonding_service.BondingManager(self)
        self._pending_config: StreamConfig | None = None
        self._user_stopping = False
        self._stalled = False
        self._last_frame = -1
        self._last_progress_at = 0.0
        self._stall_timer = QTimer(self)
        self._stall_timer.setInterval(2000)
        self._stall_timer.timeout.connect(self._check_stall)

        self._bonding.log_line.connect(self.log_line.emit)
        self._bonding.finished.connect(self._on_bonding_ready)
        self._ffmpeg.log_line.connect(self._track_progress)
        self._ffmpeg.log_line.connect(self.log_line.emit)
        self._ffmpeg.started.connect(self._on_ffmpeg_started)
        self._ffmpeg.finished.connect(self._on_ffmpeg_finished)
        self._ffmpeg.error_occurred.connect(self._on_ffmpeg_error)

    @property
    def status(self) -> StreamStatus:
        return self._status

    @property
    def bonding_busy(self) -> bool:
        return self._bonding.busy

    @property
    def is_active(self) -> bool:
        return self._status in (
            StreamStatus.STARTING,
            StreamStatus.LIVE,
            StreamStatus.STOPPING,
        )

    def start(self, config: StreamConfig) -> bool:
        if self.is_active:
            self.validation_failed.emit("Já existe uma transmissão em andamento.")
            return False

        errors = config.validate()
        if not self._ffmpeg.ffmpeg_available():
            errors.append("FFmpeg não encontrado.")

        if errors:
            self.validation_failed.emit("\n".join(errors))
            return False

        if self._bonding.busy:
            self.validation_failed.emit(
                "Aguarde: o bonding ainda está sendo configurado em segundo plano."
            )
            return False

        self._user_stopping = False
        self._set_status(StreamStatus.STARTING)

        camera = config.camera.strip()
        mic = config.microphone.strip()
        channels = "estéreo" if config.audio_channels >= 2 else "mono"
        self.log_line.emit(
            f"Câmera: {camera} · Mic: {mic} ({channels}) · "
            f"{config.resolution}@{config.fps} · {config.bitrate_kbps} kbps"
        )

        if config.bonding_configured:
            self._pending_config = config
            self._bonding.prepare(
                config.bonding_server,
                config.bonding_port,
                config.bonding_uuid,
            )
        else:
            self.log_line.emit(
                "Bonding opcional não configurado — transmitindo sem agregação."
            )
            self._launch_ffmpeg(config)
        return True

    def stop(self) -> None:
        if self._pending_config is not None:
            self._pending_config = None
            self._set_status(StreamStatus.OFFLINE)
            self.log_line.emit(
                "Transmissão cancelada — o bonding termina de configurar em segundo plano."
            )
            return

        if not self.is_active and not self._ffmpeg.is_running():
            return

        self._user_stopping = True
        self._set_status(StreamStatus.STOPPING)
        self._ffmpeg.stop()

    def _on_bonding_ready(self, _ok: bool, message: str) -> None:
        self.log_line.emit(message)
        config, self._pending_config = self._pending_config, None
        if config is None or self._status != StreamStatus.STARTING:
            return
        self._launch_ffmpeg(config)

    def _launch_ffmpeg(self, config: StreamConfig) -> None:
        self.log_line.emit(
            f"Publicando SRT → {config.vps_host.strip()}:{config.srt_port} / "
            f"{config.stream_id.strip()}"
        )
        self._ffmpeg.start(config)

    def _set_status(self, status: StreamStatus) -> None:
        if status == self._status:
            return
        self._status = status
        self.status_changed.emit(status.value)

    def _on_ffmpeg_started(self) -> None:
        self._stalled = False
        self._last_frame = -1
        self._last_progress_at = time.monotonic()
        self._stall_timer.start()
        self._set_status(StreamStatus.LIVE)

    def _track_progress(self, line: str) -> None:
        match = _FRAME_RE.search(line)
        if match and int(match.group(1)) > self._last_frame:
            self._last_frame = int(match.group(1))
            self._last_progress_at = time.monotonic()

    def _check_stall(self) -> None:
        if self._status != StreamStatus.LIVE or not self._ffmpeg.is_running():
            return
        limit = STALL_TIMEOUT_S if self._last_frame >= 0 else STALL_FIRST_FRAME_S
        idle = time.monotonic() - self._last_progress_at
        if idle < limit:
            return
        self._stalled = True
        self._stall_timer.stop()
        self.log_line.emit(
            f"Câmera travada: nenhum quadro novo há {idle:.0f} s — reiniciando a captura."
        )
        self._ffmpeg.kill()

    def _on_ffmpeg_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        self._stall_timer.stop()
        if self._user_stopping:
            self._set_status(StreamStatus.OFFLINE)
            self.log_line.emit("Transmissão encerrada.")
            self._user_stopping = False
            return

        # Sem pedido do usuário, qualquer saída é queda (câmera removida pode sair com código 0)
        if self._stalled:
            message = "Transmissão interrompida: câmera travada."
        elif exit_status == QProcess.ExitStatus.CrashExit or exit_code != 0:
            hint = ""
            if exit_code in (1, 251, 4294967041):
                hint = " Confira câmera/mic, canais ALSA e Host/SRT da VPS."
            message = f"Transmissão falhou (código {exit_code}).{hint}"
        else:
            message = "Transmissão interrompida: o FFmpeg encerrou sozinho (câmera/mic sumiu?)."
        self.log_line.emit(message)
        for warning in power_warnings():
            self.log_line.emit(warning)
        self._set_status(StreamStatus.ERROR)

    def _on_ffmpeg_error(self, message: str) -> None:
        if self._stalled or self._user_stopping:
            return
        self._stall_timer.stop()
        self.log_line.emit(message)
        self._set_status(StreamStatus.ERROR)
