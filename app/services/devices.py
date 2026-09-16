"""Detecção de câmeras e microfones (Windows DirectShow / Linux V4L2+ALSA)."""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeviceInfo:
    """Dispositivo de captura com rótulo amigável e valor usado pelo FFmpeg."""

    label: str
    value: str


def list_cameras() -> list[DeviceInfo]:
    system = platform.system()
    if system == "Windows":
        return _list_windows_dshow_devices(video=True)
    if system == "Linux":
        return _list_linux_cameras()
    return []


def list_microphones() -> list[DeviceInfo]:
    system = platform.system()
    if system == "Windows":
        return _list_windows_dshow_devices(video=False)
    if system == "Linux":
        return _list_linux_microphones()
    return []


def default_camera() -> str:
    system = platform.system()
    if system == "Linux":
        return "/dev/video0"
    cameras = list_cameras()
    return cameras[0].value if cameras else ""


def default_microphone() -> str:
    system = platform.system()
    if system == "Linux":
        return "hw:3,0"
    microphones = list_microphones()
    return microphones[0].value if microphones else ""


def _list_linux_cameras() -> list[DeviceInfo]:
    devices: list[DeviceInfo] = []
    video_root = Path("/dev")
    if not video_root.exists():
        return devices

    for path in sorted(video_root.glob("video*")):
        devices.append(DeviceInfo(label=str(path), value=str(path)))

    if not devices:
        devices.append(DeviceInfo(label="/dev/video0", value="/dev/video0"))
    return devices


def _list_linux_microphones() -> list[DeviceInfo]:
    """Lista dispositivos ALSA via `arecord -l` quando disponível."""
    devices: list[DeviceInfo] = []
    try:
        result = subprocess.run(
            ["arecord", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = result.stdout + result.stderr
    except (OSError, subprocess.TimeoutExpired):
        output = ""

    # card 3: Device [...], device 0: USB Audio [...]
    pattern = re.compile(
        r"card\s+(\d+):[^\n]*device\s+(\d+):\s*([^\n]+)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(output):
        card, device, name = match.group(1), match.group(2), match.group(3).strip()
        value = f"hw:{card},{device}"
        label = f"{value} — {name}"
        devices.append(DeviceInfo(label=label, value=value))

    if not devices:
        devices.append(DeviceInfo(label="hw:3,0", value="hw:3,0"))
        devices.append(DeviceInfo(label="default", value="default"))
    return devices


def _list_windows_dshow_devices(*, video: bool) -> list[DeviceInfo]:
    """Usa `ffmpeg -list_devices true -f dshow -i dummy` para listar DirectShow."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-list_devices",
                "true",
                "-f",
                "dshow",
                "-i",
                "dummy",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stderr + result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return []

    return _parse_dshow_devices(output, video=video)


def _parse_dshow_devices(output: str, *, video: bool) -> list[DeviceInfo]:
    devices: list[DeviceInfo] = []
    section: str | None = None
    # Ex.: [dshow @ ...] "Integrated Camera" (video)
    name_pattern = re.compile(r'"([^"]+)"\s*\((video|audio)\)', re.IGNORECASE)
    # Algumas builds listam só o nome entre aspas após o cabeçalho
    quoted_pattern = re.compile(r'^\s*\[dshow[^\]]*\]\s*"([^"]+)"\s*$')

    for line in output.splitlines():
        lower = line.lower()
        if "directshow video devices" in lower:
            section = "video"
            continue
        if "directshow audio devices" in lower:
            section = "audio"
            continue
        if "alternative name" in lower:
            continue

        match = name_pattern.search(line)
        if match:
            name = match.group(1)
            kind = match.group(2).lower()
            if video and kind == "video":
                devices.append(DeviceInfo(label=name, value=name))
            elif not video and kind == "audio":
                devices.append(DeviceInfo(label=name, value=name))
            continue

        if section == ("video" if video else "audio"):
            quoted = quoted_pattern.search(line)
            if quoted:
                name = quoted.group(1)
                devices.append(DeviceInfo(label=name, value=name))

    # Remove duplicatas preservando ordem
    seen: set[str] = set()
    unique: list[DeviceInfo] = []
    for device in devices:
        if device.value in seen:
            continue
        seen.add(device.value)
        unique.append(device)
    return unique
