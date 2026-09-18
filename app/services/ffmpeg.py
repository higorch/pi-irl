"""Serviço FFmpeg: montagem de comando e execução via QProcess."""

from __future__ import annotations

import platform
import shutil

from PySide6.QtCore import QObject, QProcess, Signal

from app.models.stream_config import StreamConfig


class FFmpegService(QObject):
    """Executa o FFmpeg como processo externo e emite logs/status."""

    log_line = Signal(str)
    started = Signal()
    finished = Signal(int, QProcess.ExitStatus)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_ready_read)
        self._process.started.connect(self._on_started)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

    def ffmpeg_available(self) -> bool:
        return self.resolve_ffmpeg_path() is not None

    @staticmethod
    def resolve_ffmpeg_path() -> str | None:
        """Retorna o caminho do FFmpeg no PATH, ou None se não existir."""
        return shutil.which("ffmpeg")

    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def build_command(self, config: StreamConfig) -> list[str]:
        """Monta a lista de argumentos do FFmpeg conforme a plataforma."""
        system = platform.system()
        if system == "Windows":
            return self._build_windows_command(config)
        return self._build_linux_command(config)

    def start(self, config: StreamConfig) -> None:
        if self.is_running():
            self.error_occurred.emit("FFmpeg já está em execução.")
            return

        if not self.ffmpeg_available():
            self.error_occurred.emit("FFmpeg não encontrado.")
            return

        args = self.build_command(config)
        program = args[0]
        program_args = args[1:]

        self.log_line.emit(f"Comando: {' '.join(args)}")
        self.log_line.emit("Iniciando FFmpeg...")
        self._process.start(program, program_args)

    def stop(self, timeout_ms: int = 5000) -> None:
        if not self.is_running():
            return

        self.log_line.emit("Parando FFmpeg...")
        self._process.terminate()
        if not self._process.waitForFinished(timeout_ms):
            self.log_line.emit("FFmpeg não encerrou a tempo; forçando encerramento.")
            self._process.kill()
            self._process.waitForFinished(3000)

    def _encode_args(self, config: StreamConfig) -> list[str]:
        """libx264 + AAC otimizados para 720p24 IRL (qualidade + latência baixa)."""
        maxrate = int(config.bitrate_kbps * 1.15)
        bufsize = config.bitrate_kbps * 2
        audio_bitrate = "160k"
        return [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-profile:v",
            "main",
            "-pix_fmt",
            "yuv420p",
            "-g",
            str(config.gop),
            "-keyint_min",
            str(config.gop),
            "-sc_threshold",
            "0",
            "-bf",
            "0",
            "-b:v",
            f"{config.bitrate_kbps}k",
            "-maxrate",
            f"{maxrate}k",
            "-bufsize",
            f"{bufsize}k",
            "-c:a",
            "aac",
            "-ar",
            str(config.sample_rate),
            "-ac",
            str(config.audio_channels),
            "-b:a",
            audio_bitrate,
            "-f",
            "mpegts",
            config.build_srt_url(),
        ]

    def _build_linux_command(self, config: StreamConfig) -> list[str]:
        """V4L2 MJPEG + ALSA → libx264 + AAC → MPEG-TS → SRT caller."""
        ffmpeg = self.resolve_ffmpeg_path() or "ffmpeg"
        return [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "info",
            "-f",
            "v4l2",
            "-input_format",
            "mjpeg",
            "-video_size",
            config.resolution,
            "-framerate",
            str(config.fps),
            "-i",
            config.camera,
            "-f",
            "alsa",
            "-thread_queue_size",
            "512",
            "-i",
            config.microphone,
            "-r",
            str(config.fps),
            *self._encode_args(config),
        ]

    def _build_windows_command(self, config: StreamConfig) -> list[str]:
        """DirectShow (dshow) para testes no Windows."""
        ffmpeg = self.resolve_ffmpeg_path() or "ffmpeg"
        video = f"video={config.camera}"
        audio = f"audio={config.microphone}"
        return [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "info",
            "-f",
            "dshow",
            "-framerate",
            str(config.fps),
            "-video_size",
            config.resolution,
            "-i",
            f"{video}:{audio}",
            "-r",
            str(config.fps),
            *self._encode_args(config),
        ]

    def _on_ready_read(self) -> None:
        data = self._process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                self.log_line.emit(stripped)

    def _on_started(self) -> None:
        self.started.emit()

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self.finished.emit(exit_code, exit_status)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.error_occurred.emit("Falha ao iniciar o FFmpeg.")
        elif error == QProcess.ProcessError.Crashed:
            self.error_occurred.emit("FFmpeg encerrou de forma inesperada.")
        else:
            self.error_occurred.emit(f"Erro no processo FFmpeg: {error.name}.")
