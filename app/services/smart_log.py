"""Filtro de log leve: eventos úteis + saúde 1 Hz, sem spam do FFmpeg."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass


_STATS_RE = re.compile(
    r"bitrate=\s*([0-9.]+)\s*kbits/s|fps=\s*([0-9.]+)",
    re.IGNORECASE,
)
_NOISE_RE = re.compile(
    r"^(frame=|size=|time=|speed=|progress=|last message repeated|"
    r"Press \[q\]|Input #\d|Output #\d|Stream mapping|Metadata:|"
    r"encoder\s+|Duration:|Start:\s|built with|configuration:)",
    re.IGNORECASE,
)

_ERROR_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"cannot set channel count", re.I),
        "Microfone: falha ao abrir canais (tente outro device / mono).",
    ),
    (
        re.compile(r"No such device|Não existe|Input/output error", re.I),
        "Dispositivo de captura indisponível.",
    ),
    (
        re.compile(r"Connection timed out|Connection refused|Failed to open", re.I),
        "Falha de rede ao publicar SRT (Host/porta/firewall?).",
    ),
    (
        re.compile(r"Error opening input|Could not open", re.I),
        "Não foi possível abrir câmera ou microfone.",
    ),
    (
        re.compile(r"Permission denied", re.I),
        "Permissão negada no device (usuário no grupo video/audio?).",
    ),
)


@dataclass
class HealthStats:
    bitrate_kbps: float | None = None
    fps: float | None = None

    def label(self) -> str:
        parts: list[str] = []
        if self.bitrate_kbps is not None:
            mbps = self.bitrate_kbps / 1000.0
            parts.append(f"~{mbps:.1f} Mb/s")
        if self.fps is not None:
            parts.append(f"{self.fps:.0f} fps")
        if not parts:
            return "Saúde: capturando…"
        return "Saúde: " + " · ".join(parts) + " · A/V ok"


class SmartLogFilter:
    """Transforma linhas brutas em eventos (ou None) e atualiza saúde."""

    def __init__(self, *, min_health_interval_s: float = 1.0) -> None:
        self._last_health_at = 0.0
        self._min_health_interval_s = min_health_interval_s
        self.health = HealthStats()

    def process(self, raw: str) -> tuple[str | None, HealthStats | None]:
        """
        Retorna (evento_para_log | None, health_atualizado | None).

        health só é emitido no máximo a cada min_health_interval_s.
        """
        line = (raw or "").strip()
        if not line:
            return None, None

        # Linha de progresso do FFmpeg
        if "bitrate=" in line.lower() or re.search(r"\bfps=\s*\d", line, re.I):
            self._ingest_stats(line)
            now = time.monotonic()
            if now - self._last_health_at >= self._min_health_interval_s:
                self._last_health_at = now
                return None, self.health
            return None, None

        if _NOISE_RE.search(line):
            return None, None

        for pattern, message in _ERROR_HINTS:
            if pattern.search(line):
                return message, None

        # Warnings/erros curtos do FFmpeg
        lower = line.lower()
        if any(token in lower for token in ("error", "failed", "fatal", "warning")):
            # Evita flood: corta linhas enormes
            return _shorten(line, 160), None

        # Eventos do próprio app (já em português) passam direto
        app_prefixes = (
            "Bonding",
            "Câmera",
            "Publicando",
            "Ao vivo",
            "Transmissão",
            "Perfil",
            "RTSP",
            "URL SRT",
            "FFmpeg",
            "Dispositivos",
            "Microfone",
            "Iniciando",
            "Parando",
            "Saúde",
        )
        if any(line.startswith(prefix) for prefix in app_prefixes):
            return line, None

        # Demais linhas brutas: só se forem curtas e relevantes
        if len(line) <= 120 and ("srt" in lower or "alsa" in lower or "v4l2" in lower):
            return _shorten(line, 160), None

        return None, None

    def _ingest_stats(self, line: str) -> None:
        bitrate = None
        fps = None
        for match in _STATS_RE.finditer(line):
            if match.group(1):
                try:
                    bitrate = float(match.group(1))
                except ValueError:
                    pass
            if match.group(2):
                try:
                    fps = float(match.group(2))
                except ValueError:
                    pass
        # Também captura padrões juntos na mesma linha
        br = re.search(r"bitrate=\s*([0-9.]+)\s*kbits", line, re.I)
        if br:
            try:
                bitrate = float(br.group(1))
            except ValueError:
                pass
        fp = re.search(r"fps=\s*([0-9.]+)", line, re.I)
        if fp:
            try:
                fps = float(fp.group(1))
            except ValueError:
                pass
        if bitrate is not None:
            self.health.bitrate_kbps = bitrate
        if fps is not None:
            self.health.fps = fps


def _shorten(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
