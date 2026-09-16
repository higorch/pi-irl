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
    cameras = list_cameras()
    return cameras[0].value if cameras else ""


def default_microphone() -> str:
    microphones = list_microphones()
    return microphones[0].value if microphones else ""


def _list_linux_cameras() -> list[DeviceInfo]:
    """Lista apenas nós V4L2 com capacidade real de captura de vídeo."""
    devices: list[DeviceInfo] = []
    video_root = Path("/dev")
    if not video_root.exists():
        return devices

    for path in sorted(video_root.glob("video*")):
        if not path.is_char_device() and not path.exists():
            continue
        if not _is_v4l2_video_capture(path):
            continue
        name = _v4l2_device_name(path)
        label = f"{path} — {name}" if name else str(path)
        devices.append(DeviceInfo(label=label, value=str(path)))

    return _unique_devices(devices)


def _is_v4l2_video_capture(path: Path) -> bool:
    """True somente se o device expõe formatos de captura (não metadata/output)."""
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", str(path), "--list-formats-ext"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return False

    lower = output.lower()
    if not output.strip():
        return False
    if "inappropriate ioctl" in lower or "invalid argument" in lower:
        return False

    # Nós de captura listam pixel formats / tamanhos; metadata/output não.
    has_pixel_format = "pixel format" in lower
    has_size = re.search(r"Size:\s*(Discrete|Stepwise)", output, re.IGNORECASE) is not None
    return has_pixel_format or has_size


def _v4l2_device_name(path: Path) -> str:
    sys_name = Path("/sys/class/video4linux") / path.name / "name"
    try:
        if sys_name.exists():
            return sys_name.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        pass

    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", str(path), "--info"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        match = re.search(
            r"Card\s+type\s*:\s*(.+)$",
            result.stdout or "",
            re.IGNORECASE | re.MULTILINE,
        )
        if match:
            return match.group(1).strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def _list_linux_microphones() -> list[DeviceInfo]:
    """Lista somente placas/dispositivos ALSA reportados por `arecord -l`."""
    devices: list[DeviceInfo] = []
    try:
        result = subprocess.run(
            ["arecord", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return devices

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

    return _unique_devices(devices)


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
    name_pattern = re.compile(r'"([^"]+)"\s*\((video|audio)\)', re.IGNORECASE)
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

    return _unique_devices(devices)


def _unique_devices(devices: list[DeviceInfo]) -> list[DeviceInfo]:
    seen: set[str] = set()
    unique: list[DeviceInfo] = []
    for device in devices:
        if device.value in seen:
            continue
        seen.add(device.value)
        unique.append(device)
    return unique
