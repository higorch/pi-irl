"""Orquestração da transmissão IRL."""

from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, Signal

from app.models.stream_config import StreamConfig, StreamStatus
from app.services.ffmpeg import FFmpegService


class StreamService(QObject):
    """Coordena status, validação e ciclo de vida do FFmpeg."""

    status_changed = Signal(str)
    log_line = Signal(str)
    validation_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._status = StreamStatus.OFFLINE
        self._ffmpeg = FFmpegService(self)
        self._user_stopping = False

        self._ffmpeg.log_line.connect(self.log_line.emit)
        self._ffmpeg.started.connect(self._on_ffmpeg_started)
        self._ffmpeg.finished.connect(self._on_ffmpeg_finished)
        self._ffmpeg.error_occurred.connect(self._on_ffmpeg_error)

    @property
    def status(self) -> StreamStatus:
        return self._status

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

        self._user_stopping = False
        self._set_status(StreamStatus.STARTING)
        self.log_line.emit(f"URL SRT: {config.build_srt_url()}")
        self.log_line.emit(f"RTSP esperado: {config.build_rtsp_url()}")
        self._ffmpeg.start(config)
        return True

    def stop(self) -> None:
        if not self.is_active and not self._ffmpeg.is_running():
            return

        self._user_stopping = True
        self._set_status(StreamStatus.STOPPING)
        self._ffmpeg.stop()

    def _set_status(self, status: StreamStatus) -> None:
        self._status = status
        self.status_changed.emit(status.value)

    def _on_ffmpeg_started(self) -> None:
        self._set_status(StreamStatus.LIVE)
        self.log_line.emit("Transmissão iniciada.")

    def _on_ffmpeg_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        if self._user_stopping:
            self._set_status(StreamStatus.OFFLINE)
            self.log_line.emit("Transmissão encerrada.")
            self._user_stopping = False
            return

        if exit_status == QProcess.ExitStatus.CrashExit or exit_code != 0:
            self._set_status(StreamStatus.ERROR)
            self.log_line.emit(
                f"FFmpeg encerrou inesperadamente (código {exit_code})."
            )
        else:
            self._set_status(StreamStatus.OFFLINE)
            self.log_line.emit("FFmpeg finalizou.")

    def _on_ffmpeg_error(self, message: str) -> None:
        self._set_status(StreamStatus.ERROR)
        self.log_line.emit(message)
