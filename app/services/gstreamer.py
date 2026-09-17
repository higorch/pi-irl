"""Serviço GStreamer: montagem de pipeline e execução via QProcess."""

from __future__ import annotations

import platform
import shutil

from PySide6.QtCore import QObject, QProcess, Signal

from app.models.stream_config import StreamConfig


class GStreamerService(QObject):
    """Executa gst-launch-1.0 como processo externo e emite logs/status."""

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

    def gstreamer_available(self) -> bool:
        return self.resolve_gst_launch_path() is not None

    @staticmethod
    def resolve_gst_launch_path() -> str | None:
        """Retorna o caminho do gst-launch-1.0 no PATH, ou None."""
        return shutil.which("gst-launch-1.0") or shutil.which("gst-launch-1.0.exe")

    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def build_command(self, config: StreamConfig) -> list[str]:
        """Monta gst-launch-1.0 + elementos do pipeline conforme a plataforma."""
        launch = self.resolve_gst_launch_path() or "gst-launch-1.0"
        system = platform.system()
        if system == "Windows":
            pipeline = self._build_windows_pipeline(config)
        else:
            pipeline = self._build_linux_pipeline(config)
        return [launch, "-e", "-v", *pipeline]

    def start(self, config: StreamConfig) -> None:
        if self.is_running():
            self.error_occurred.emit("GStreamer já está em execução.")
            return

        if not self.gstreamer_available():
            self.error_occurred.emit("GStreamer (gst-launch-1.0) não encontrado.")
            return

        args = self.build_command(config)
        program = args[0]
        program_args = args[1:]

        self.log_line.emit(f"Comando: {' '.join(args)}")
        self.log_line.emit("Iniciando GStreamer...")
        self._process.start(program, program_args)

    def stop(self, timeout_ms: int = 5000) -> None:
        if not self.is_running():
            return

        self.log_line.emit("Parando GStreamer...")
        # -e faz o pipeline finalizar no EOS; terminate encerra o processo
        self._process.terminate()
        if not self._process.waitForFinished(timeout_ms):
            self.log_line.emit("GStreamer não encerrou a tempo; forçando encerramento.")
            self._process.kill()
            self._process.waitForFinished(3000)

    def _parse_resolution(self, config: StreamConfig) -> tuple[str, str]:
        width, height = config.resolution.lower().split("x", 1)
        return width.strip(), height.strip()

    def _build_linux_pipeline(self, config: StreamConfig) -> list[str]:
        """V4L2 MJPEG + ALSA → x264 + AAC → MPEG-TS → SRT caller."""
        width, height = self._parse_resolution(config)
        srt_uri = config.build_srt_url()
        video_caps = (
            f"image/jpeg,width={width},height={height},"
            f"framerate={config.fps}/1"
        )
        audio_caps = (
            f"audio/x-raw,channels={config.audio_channels},"
            f"rate={config.sample_rate}"
        )

        return [
            "v4l2src",
            f"device={config.camera}",
            "!",
            video_caps,
            "!",
            "jpegdec",
            "!",
            "videoconvert",
            "!",
            "x264enc",
            "tune=zerolatency",
            "speed-preset=ultrafast",
            f"bitrate={config.bitrate_kbps}",
            f"key-int-max={config.gop}",
            "!",
            "video/x-h264,profile=baseline",
            "!",
            "h264parse",
            "!",
            "queue",
            "!",
            "mux.",
            "alsasrc",
            f"device={config.microphone}",
            "!",
            "audioconvert",
            "!",
            "audioresample",
            "!",
            audio_caps,
            "!",
            "avenc_aac",
            "bitrate=128000",
            "!",
            "aacparse",
            "!",
            "queue",
            "!",
            "mux.",
            "mpegtsmux",
            "name=mux",
            "alignment=7",
            "!",
            "srtsink",
            f"uri={srt_uri}",
            "wait-for-connection=false",
        ]

    def _build_windows_pipeline(self, config: StreamConfig) -> list[str]:
        """Pipeline DirectShow (dshow*) para testes no Windows."""
        width, height = self._parse_resolution(config)
        srt_uri = config.build_srt_url()
        video_caps = (
            f"video/x-raw,width={width},height={height},"
            f"framerate={config.fps}/1"
        )
        audio_caps = (
            f"audio/x-raw,channels={config.audio_channels},"
            f"rate={config.sample_rate}"
        )

        return [
            "dshowvideosrc",
            f"device-name={config.camera}",
            "!",
            "videoconvert",
            "!",
            "videoscale",
            "!",
            video_caps,
            "!",
            "x264enc",
            "tune=zerolatency",
            "speed-preset=ultrafast",
            f"bitrate={config.bitrate_kbps}",
            f"key-int-max={config.gop}",
            "!",
            "video/x-h264,profile=baseline",
            "!",
            "h264parse",
            "!",
            "queue",
            "!",
            "mux.",
            "dshowaudiosrc",
            f"device-name={config.microphone}",
            "!",
            "audioconvert",
            "!",
            "audioresample",
            "!",
            audio_caps,
            "!",
            "avenc_aac",
            "bitrate=128000",
            "!",
            "aacparse",
            "!",
            "queue",
            "!",
            "mux.",
            "mpegtsmux",
            "name=mux",
            "alignment=7",
            "!",
            "srtsink",
            f"uri={srt_uri}",
            "wait-for-connection=false",
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
            self.error_occurred.emit("Falha ao iniciar o GStreamer.")
        elif error == QProcess.ProcessError.Crashed:
            self.error_occurred.emit("GStreamer encerrou de forma inesperada.")
        else:
            self.error_occurred.emit(f"Erro no processo GStreamer: {error.name}.")
