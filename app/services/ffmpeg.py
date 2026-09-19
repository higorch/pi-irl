"""Serviço FFmpeg: montagem de comando e execução via QProcess."""

from __future__ import annotations

import shutil

from PySide6.QtCore import QObject, QProcess, Signal

from app.models.stream_config import StreamConfig
from app.services.media_profile import MediaProfile, probe_best_profile
from app.services.sources import SourceKind, classify_audio, classify_video, is_network_url


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

    def build_command(
        self,
        config: StreamConfig,
        profile: MediaProfile | None = None,
    ) -> list[str]:
        """Monta o comando conforme o tipo de fonte (local ou rede)."""
        camera = (config.camera or "").strip()
        microphone = (config.microphone or "").strip()
        if not camera:
            raise ValueError("Câmera vazia.")
        if not microphone:
            raise ValueError("Microfone vazio.")

        if profile is None:
            profile = probe_best_profile(
                camera,
                microphone,
                output_resolution=config.resolution,
                output_fps=config.fps,
                bitrate_kbps=config.bitrate_kbps,
            )

        ffmpeg = self.resolve_ffmpeg_path() or "ffmpeg"
        video_kind = classify_video(camera)
        audio_kind = classify_audio(microphone)

        args: list[str] = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "info",
            "-fflags",
            "+genpts",
        ]

        args += self._video_input_args(config, profile, video_kind)

        if audio_kind == SourceKind.FROM_CAMERA:
            audio_input = 0
        else:
            args += self._audio_input_args(config, profile, audio_kind)
            audio_input = 1

        args += self._encode_args(config, profile, audio_input=audio_input)
        return args

    def start(self, config: StreamConfig) -> None:
        if self.is_running():
            self.error_occurred.emit("FFmpeg já está em execução.")
            return

        if not self.ffmpeg_available():
            self.error_occurred.emit("FFmpeg não encontrado.")
            return

        try:
            profile = probe_best_profile(
                config.camera,
                config.microphone,
                output_resolution=config.resolution,
                output_fps=config.fps,
                bitrate_kbps=config.bitrate_kbps,
            )
            config.gop = profile.gop
            config.sample_rate = profile.sample_rate
            config.audio_channels = profile.audio_channels

            self.log_line.emit(f"Perfil: {profile.summary}")
            args = self.build_command(config, profile)
        except ValueError as exc:
            self.error_occurred.emit(str(exc))
            return

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

    def _encode_args(
        self,
        config: StreamConfig,
        profile: MediaProfile,
        *,
        audio_input: int,
    ) -> list[str]:
        maxrate = int(profile.bitrate_kbps * 1.15)
        bufsize = max(profile.bitrate_kbps, int(profile.bitrate_kbps * 0.75))
        channels = 2 if profile.audio_channels >= 2 else 1
        audio_bitrate = "192k" if channels == 2 else "160k"
        vf = (
            f"fps={profile.output_fps},"
            f"scale={profile.output_width}:{profile.output_height},"
            "format=yuv420p"
        )
        return [
            "-map",
            "0:v:0",
            "-map",
            f"{audio_input}:a:0",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-profile:v",
            "baseline",
            "-g",
            str(profile.gop),
            "-keyint_min",
            str(profile.gop),
            "-sc_threshold",
            "0",
            "-bf",
            "0",
            "-flags",
            "+low_delay",
            "-b:v",
            f"{profile.bitrate_kbps}k",
            "-maxrate",
            f"{maxrate}k",
            "-bufsize",
            f"{bufsize}k",
            "-c:a",
            "aac",
            "-ar",
            str(profile.sample_rate),
            "-ac",
            str(channels),
            "-b:a",
            audio_bitrate,
            "-flush_packets",
            "1",
            "-muxdelay",
            "0",
            "-muxpreload",
            "0",
            "-f",
            "mpegts",
            config.build_srt_url(),
        ]

    def _video_input_args(
        self,
        config: StreamConfig,
        profile: MediaProfile,
        kind: SourceKind,
    ) -> list[str]:
        if kind == SourceKind.NETWORK:
            return self._network_input_args(config.camera)
        if kind == SourceKind.DSHOW:
            return [
                "-thread_queue_size",
                "512",
                "-f",
                "dshow",
                "-i",
                f"video={config.camera.strip()}",
            ]
        # V4L2
        return [
            "-thread_queue_size",
            "512",
            "-f",
            "v4l2",
            "-input_format",
            profile.input_format,
            "-video_size",
            profile.capture_size,
            "-framerate",
            str(profile.capture_fps),
            "-i",
            config.camera.strip(),
        ]

    def _audio_input_args(
        self,
        config: StreamConfig,
        profile: MediaProfile,
        kind: SourceKind,
    ) -> list[str]:
        if kind == SourceKind.NETWORK:
            return self._network_input_args(config.microphone)
        if kind == SourceKind.DSHOW:
            return [
                "-thread_queue_size",
                "512",
                "-f",
                "dshow",
                "-i",
                f"audio={config.microphone.strip()}",
            ]
        # ALSA
        channels = 2 if profile.audio_channels >= 2 else 1
        return [
            "-thread_queue_size",
            "512",
            "-f",
            "alsa",
            "-ac",
            str(channels),
            "-ar",
            str(profile.sample_rate),
            "-i",
            self._alsa_device(config.microphone),
        ]

    @staticmethod
    def _network_input_args(url: str) -> list[str]:
        """RTSP/HTTP/UDP/etc. — genérico para câmeras/mics Wi‑Fi ou IP."""
        value = url.strip()
        args: list[str] = ["-thread_queue_size", "512"]
        if value.lower().startswith(("rtsp://", "rtsps://")):
            args += ["-rtsp_transport", "tcp", "-rtsp_flags", "prefer_tcp"]
        if is_network_url(value):
            args += ["-fflags", "nobuffer", "-flags", "low_delay"]
        args += ["-i", value]
        return args

    @staticmethod
    def _alsa_device(device: str) -> str:
        """Prefere plughw: para o ALSA aceitar taxa/canais com conversão."""
        value = device.strip()
        if value.startswith("hw:"):
            return "plughw:" + value[3:]
        return value

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
