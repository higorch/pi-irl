"""Classificação de fontes de vídeo/áudio para o FFmpeg."""

from __future__ import annotations

import platform
import re
from enum import Enum


# Áudio do mesmo input de vídeo (legado / streams de rede).
AUDIO_FROM_CAMERA = "@camera"

_NETWORK_RE = re.compile(
    r"^(rtsp|rtsps|http|https|udp|tcp|srt|rtmp|rtmps|mms)://",
    re.IGNORECASE,
)


class SourceKind(str, Enum):
    V4L2 = "v4l2"
    ALSA = "alsa"
    DSHOW = "dshow"
    NETWORK = "network"
    FROM_CAMERA = "from_camera"


def is_network_url(value: str) -> bool:
    return bool(_NETWORK_RE.match((value or "").strip()))


def is_audio_from_camera(value: str) -> bool:
    text = (value or "").strip().lower()
    return text in {AUDIO_FROM_CAMERA, "from:camera", "camera", "@video"}


def _local_video_kind() -> SourceKind:
    return SourceKind.DSHOW if platform.system() == "Windows" else SourceKind.V4L2


def _local_audio_kind() -> SourceKind:
    return SourceKind.DSHOW if platform.system() == "Windows" else SourceKind.ALSA


def classify_video(value: str) -> SourceKind:
    text = (value or "").strip()
    if not text:
        return _local_video_kind()
    if is_network_url(text):
        return SourceKind.NETWORK
    if platform.system() == "Windows":
        return SourceKind.DSHOW
    if text.startswith("/dev/"):
        return SourceKind.V4L2
    return SourceKind.NETWORK if "://" in text else SourceKind.V4L2


def classify_audio(value: str) -> SourceKind:
    text = (value or "").strip()
    if not text:
        return _local_audio_kind()
    if is_audio_from_camera(text):
        return SourceKind.FROM_CAMERA
    if is_network_url(text):
        return SourceKind.NETWORK
    if platform.system() == "Windows":
        return SourceKind.DSHOW
    if text.startswith(("hw:", "plughw:", "default:", "default")):
        return SourceKind.ALSA
    return SourceKind.NETWORK if "://" in text else SourceKind.ALSA
