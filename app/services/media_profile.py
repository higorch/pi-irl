"""Perfil de captura A/V: detecta modos da câmera e sugere resolução/FPS/bitrate."""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass

from app.services.sources import (
    SourceKind,
    classify_audio,
    classify_video,
    is_audio_from_camera,
)


TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
TARGET_FPS = 24

DEFAULT_RESOLUTIONS = ("1920x1080", "1280x720", "854x480", "640x480")
DEFAULT_FPS_OPTIONS = (24, 25, 30)

_FORMAT_PREFERENCE = (
    ("MJPG", "mjpeg"),
    ("JPEG", "mjpeg"),
    ("YUYV", "yuyv422"),
    ("YUY2", "yuyv422"),
    ("NV12", "nv12"),
)


@dataclass(frozen=True)
class MediaProfile:
    """Modo de captura + encode para a transmissão."""

    input_format: str
    capture_width: int
    capture_height: int
    capture_fps: int
    output_width: int
    output_height: int
    output_fps: int
    bitrate_kbps: int
    gop: int
    sample_rate: int
    audio_channels: int
    summary: str

    @property
    def capture_size(self) -> str:
        return f"{self.capture_width}x{self.capture_height}"

    @property
    def output_size(self) -> str:
        return f"{self.output_width}x{self.output_height}"


def parse_resolution(value: str) -> tuple[int, int]:
    width, height = value.lower().split("x", 1)
    return int(width.strip()), int(height.strip())


def suggested_bitrate(width: int, height: int, fps: int) -> int:
    pixels = width * height
    if pixels >= 1920 * 1080:
        base = 6000
    elif pixels >= 1280 * 720:
        base = 4000
    elif pixels >= 854 * 480:
        base = 2500
    else:
        base = 1500
    if fps <= 24:
        return int(base * 0.95)
    if fps >= 30:
        return int(base * 1.05)
    return base


def list_resolution_choices(camera: str = "") -> list[str]:
    """Resoluções selecionáveis (padrões + as que a câmera oferece)."""
    found: set[str] = set(DEFAULT_RESOLUTIONS)
    modes = _all_modes_for_camera(camera)
    for w, h, _fps in modes:
        found.add(f"{w}x{h}")
    return _sort_resolutions(found)


def list_fps_choices(camera: str = "") -> list[int]:
    """FPS selecionáveis (padrões + os que a câmera oferece)."""
    found: set[int] = set(DEFAULT_FPS_OPTIONS)
    for _w, _h, fps in _all_modes_for_camera(camera):
        if 1 <= fps <= 60:
            found.add(fps)
    return sorted(found)


def recommend_defaults(camera: str, microphone: str = "") -> tuple[str, int, int]:
    """
    Sugere (resolução, fps, bitrate) com base na câmera.

    Prioriza 720p24 quando a câmera aguenta; senão o melhor modo disponível.
    """
    profile = probe_best_profile(camera, microphone)
    return profile.output_size, profile.output_fps, profile.bitrate_kbps


def probe_best_profile(
    camera: str,
    microphone: str = "",
    *,
    output_resolution: str | None = None,
    output_fps: int | None = None,
    bitrate_kbps: int | None = None,
) -> MediaProfile:
    """Monta perfil de captura adequado ao alvo de saída escolhido."""
    if output_resolution:
        out_w, out_h = parse_resolution(output_resolution)
    else:
        out_w, out_h = TARGET_WIDTH, TARGET_HEIGHT

    out_fps = int(output_fps) if output_fps else TARGET_FPS

    system = platform.system()
    video_kind = classify_video(camera)
    audio_kind = classify_audio(microphone) if microphone else None

    if video_kind == SourceKind.V4L2 and system == "Linux":
        video = _probe_linux_video(camera, target_w=out_w, target_h=out_h)
    else:
        video = None

    if (
        audio_kind == SourceKind.ALSA
        and system == "Linux"
        and microphone
        and not is_audio_from_camera(microphone)
    ):
        audio = _probe_linux_audio(microphone)
    else:
        audio = None

    if video is None:
        capture_w, capture_h = out_w, out_h
        capture_fps = out_fps if video_kind == SourceKind.NETWORK else (
            30 if out_fps == 24 else out_fps
        )
        input_format = "mjpeg"
        if video_kind == SourceKind.NETWORK:
            fmt_label = "rede"
        elif video_kind == SourceKind.DSHOW:
            fmt_label = "dshow"
        else:
            fmt_label = "auto"
    else:
        capture_w, capture_h, capture_fps, input_format, fmt_label = video

    if audio:
        sample_rate, audio_channels = audio
    elif audio_kind in (SourceKind.FROM_CAMERA, SourceKind.NETWORK):
        sample_rate, audio_channels = 48000, 2
    else:
        # ALSA/dshow local: mono por padrão (probe ALSA sobrescreve se houver estéreo)
        sample_rate, audio_channels = 48000, 1

    bitrate = (
        int(bitrate_kbps)
        if bitrate_kbps and bitrate_kbps >= 100
        else suggested_bitrate(out_w, out_h, out_fps)
    )
    # GOP de ~1 s: menos atraso no player (trade-off: um pouco mais de bitrate em cenas dinâmicas)
    gop = max(out_fps, 1)
    audio_label = "estéreo" if audio_channels >= 2 else "mono"

    summary = (
        f"cap {capture_w}x{capture_h}@{capture_fps} ({fmt_label}) → "
        f"out {out_w}x{out_h}@{out_fps} · {bitrate} kbps · áudio {audio_label}"
    )
    return MediaProfile(
        input_format=input_format,
        capture_width=capture_w,
        capture_height=capture_h,
        capture_fps=capture_fps,
        output_width=out_w,
        output_height=out_h,
        output_fps=out_fps,
        bitrate_kbps=bitrate,
        gop=gop,
        sample_rate=sample_rate,
        audio_channels=audio_channels,
        summary=summary,
    )


def _all_modes_for_camera(camera: str) -> list[tuple[int, int, int]]:
    if not camera or classify_video(camera) != SourceKind.V4L2:
        return []
    if platform.system() != "Linux":
        return []
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", camera, "--list-formats-ext"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return []

    modes = _parse_v4l2_formats(output)
    items: list[tuple[int, int, int]] = []
    for values in modes.values():
        items.extend(values)
    return items


def _sort_resolutions(values: set[str]) -> list[str]:
    def key(item: str) -> tuple[int, int]:
        try:
            w, h = parse_resolution(item)
            return (w * h, w)
        except ValueError:
            return (0, 0)

    return sorted(values, key=key, reverse=True)


def _probe_linux_video(
    device: str,
    *,
    target_w: int,
    target_h: int,
) -> tuple[int, int, int, str, str] | None:
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", device, "--list-formats-ext"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return None

    modes = _parse_v4l2_formats(output)
    if not modes:
        return None

    best: tuple[int, int, int, str, str] | None = None
    best_score = -1

    for fourcc, ffmpeg_name in _FORMAT_PREFERENCE:
        for w, h, fps in modes.get(fourcc, []):
            score = _score_mode(w, h, fps, fourcc, target_w, target_h)
            if score > best_score:
                best_score = score
                best = (w, h, fps, ffmpeg_name, fourcc)

    return best


def _score_mode(
    width: int,
    height: int,
    fps: int,
    fourcc: str,
    target_w: int,
    target_h: int,
) -> int:
    score = 0
    if fourcc in ("MJPG", "JPEG"):
        score += 10_000
    elif fourcc in ("YUYV", "YUY2"):
        score += 5_000
    else:
        score += 1_000

    pixels = width * height
    target = target_w * target_h
    if height >= target_h and width >= target_w:
        score += 3_000
        score -= abs(pixels - target) // 1000
    elif height >= 480:
        score += 1_500
        score -= abs(pixels - target) // 500
    else:
        score += 200

    if fps == 30:
        score += 800
    elif fps in (24, 25):
        score += 700
    elif 20 <= fps <= 60:
        score += 400
    else:
        score += 50

    return score


def _parse_v4l2_formats(
    output: str,
) -> dict[str, list[tuple[int, int, int]]]:
    modes: dict[str, list[tuple[int, int, int]]] = {}
    current_fmt = ""
    current_size: tuple[int, int] | None = None

    fmt_re = re.compile(r"Pixel Format:\s*'([^']+)'", re.IGNORECASE)
    size_re = re.compile(r"Size:\s*Discrete\s+(\d+)x(\d+)", re.IGNORECASE)
    fps_re = re.compile(
        r"Interval:\s*Discrete[^(]*\(([\d.]+)\s*fps\)",
        re.IGNORECASE,
    )

    for line in output.splitlines():
        fmt_match = fmt_re.search(line)
        if fmt_match:
            current_fmt = fmt_match.group(1).strip().upper().replace(" ", "")
            modes.setdefault(current_fmt, [])
            current_size = None
            continue

        size_match = size_re.search(line)
        if size_match and current_fmt:
            current_size = (int(size_match.group(1)), int(size_match.group(2)))
            continue

        fps_match = fps_re.search(line)
        if fps_match and current_fmt and current_size:
            fps = int(round(float(fps_match.group(1))))
            if fps > 0:
                modes[current_fmt].append(
                    (current_size[0], current_size[1], fps)
                )

    for key, values in list(modes.items()):
        modes[key] = sorted(set(values), key=lambda t: (t[0] * t[1], t[2]))
    return modes


def _probe_linux_audio(device: str) -> tuple[int, int] | None:
    """
    Retorna (sample_rate, channels).

    channels = 2 se o device permitir estéreo; 1 se só mono.
    """
    raw_device = device.strip()
    candidates = [raw_device]
    if raw_device.startswith("hw:"):
        candidates.append("plughw:" + raw_device[3:])
    elif raw_device.startswith("plughw:"):
        candidates.append("hw:" + raw_device[7:])

    output = ""
    for candidate in candidates:
        try:
            result = subprocess.run(
                ["arecord", "-D", candidate, "--dump-hw-params"],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            output = (result.stdout or "") + (result.stderr or "")
            if "RATE:" in output.upper() or "CHANNELS:" in output.upper():
                break
        except (OSError, subprocess.TimeoutExpired):
            continue

    if not output:
        return None

    rates: list[int] = []
    rate_block = re.search(
        r"RATE:\s*\[([^\]]+)\]|RATE:\s*(\d+)",
        output,
        re.IGNORECASE,
    )
    if rate_block:
        raw = rate_block.group(1) or rate_block.group(2) or ""
        rates = [int(x) for x in re.findall(r"\d+", raw)]

    channels: list[int] = []
    ch_block = re.search(
        r"CHANNELS:\s*\[([^\]]+)\]|CHANNELS:\s*(\d+)",
        output,
        re.IGNORECASE,
    )
    if ch_block:
        raw = ch_block.group(1) or ch_block.group(2) or ""
        channels = [int(x) for x in re.findall(r"\d+", raw)]

    preferred_rates = (48000, 44100, 32000, 16000)
    if rates:
        sample_rate = next((r for r in preferred_rates if r in rates), max(rates))
    else:
        sample_rate = 48000

    # Estéreo se o hardware permitir 2+ canais; senão mono
    if any(ch >= 2 for ch in channels):
        audio_channels = 2
    elif 1 in channels:
        audio_channels = 1
    elif channels:
        audio_channels = min(2, max(channels))
    else:
        # Sem info clara: mono (evita erro em USB Audio 1 canal)
        audio_channels = 1

    return sample_rate, audio_channels
