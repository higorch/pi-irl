"""Detecção rápida de câmeras e microfones conectados (Windows / Linux)."""

from __future__ import annotations

import json
import platform
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeviceInfo:
    """Dispositivo de captura com rótulo amigável e valor usado pelo FFmpeg."""

    label: str
    value: str


# Cache curto: evita 2+ varreduras ao abrir a UI / refresh.
_CACHE_TTL_S = 4.0
_cache_at = 0.0
_cache_cameras: list[DeviceInfo] = []
_cache_mics: list[DeviceInfo] = []


def list_cameras() -> list[DeviceInfo]:
    cameras, _ = _list_all_cached()
    return cameras


def list_microphones() -> list[DeviceInfo]:
    _, mics = _list_all_cached()
    return mics


def default_camera() -> str:
    cameras = list_cameras()
    return cameras[0].value if cameras else ""


def default_microphone() -> str:
    microphones = list_microphones()
    return microphones[0].value if microphones else ""


def _list_all_cached() -> tuple[list[DeviceInfo], list[DeviceInfo]]:
    global _cache_at, _cache_cameras, _cache_mics
    now = time.monotonic()
    if _cache_at and (now - _cache_at) < _CACHE_TTL_S:
        return _cache_cameras, _cache_mics

    system = platform.system()
    if system == "Windows":
        cameras, mics = _list_windows_all()
    elif system == "Linux":
        cameras, mics = _list_linux_cameras(), _list_linux_microphones()
    else:
        cameras, mics = [], []

    _cache_cameras = cameras
    _cache_mics = mics
    _cache_at = now
    return cameras, mics


def _list_linux_cameras() -> list[DeviceInfo]:
    """Câmeras V4L2 presentes com captura (USB, CSI, etc.) — uma varredura rápida."""
    devices: list[DeviceInfo] = []
    # Um único comando: agrupa nós por dispositivo físico; o 1º /dev/video* costuma ser captura.
    grouped = _v4l2_list_devices_groups()
    if grouped:
        for name, paths in grouped:
            if not paths:
                continue
            path = paths[0]
            label = f"{path} — {name}" if name else path
            devices.append(DeviceInfo(label=label, value=path))
        return _unique_devices(devices)

    # Fallback sem v4l2-ctl --list-devices
    video_root = Path("/dev")
    if not video_root.exists():
        return devices

    for path in sorted(video_root.glob("video*")):
        if not path.exists():
            continue
        name = _v4l2_sysfs_name(path)
        if _looks_like_metadata_node(name):
            continue
        if not _is_v4l2_video_capture_fast(path):
            continue
        label = f"{path} — {name}" if name else str(path)
        devices.append(DeviceInfo(label=label, value=str(path)))

    return _unique_devices(devices)


def _v4l2_list_devices_groups() -> list[tuple[str, list[str]]]:
    """Parse de `v4l2-ctl --list-devices` → [(nome, [/dev/videoN, ...]), ...]."""
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--list-devices"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        output = result.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        return []

    groups: list[tuple[str, list[str]]] = []
    current_name = ""
    current_paths: list[str] = []

    for line in output.splitlines():
        if not line.strip():
            continue
        if not line.startswith("\t") and not line.startswith(" "):
            if current_name or current_paths:
                groups.append((current_name, current_paths))
            current_name = line.strip().rstrip(":")
            current_paths = []
            continue
        path = line.strip()
        if path.startswith("/dev/video"):
            current_paths.append(path)

    if current_name or current_paths:
        groups.append((current_name, current_paths))

    return groups


def _v4l2_sysfs_name(path: Path) -> str:
    sys_name = Path("/sys/class/video4linux") / path.name / "name"
    try:
        if sys_name.exists():
            return sys_name.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        pass
    return ""


def _looks_like_metadata_node(name: str) -> bool:
    lower = name.lower()
    return any(token in lower for token in ("metadata", "meta", "infrared", " ir "))


def _is_v4l2_video_capture_fast(path: Path) -> bool:
    """Checagem leve: formatos via v4l2-ctl com timeout curto."""
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", str(path), "--list-formats-ext"],
            capture_output=True,
            text=True,
            timeout=2,
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
    return "pixel format" in lower or re.search(
        r"Size:\s*(Discrete|Stepwise)", output, re.IGNORECASE
    )


def _list_linux_microphones() -> list[DeviceInfo]:
    """Todas as entradas de captura ALSA presentes (USB, jack, etc.)."""
    devices: list[DeviceInfo] = []
    try:
        result = subprocess.run(
            ["arecord", "-l"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return devices

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


def _list_windows_all() -> tuple[list[DeviceInfo], list[DeviceInfo]]:
    """Uma única chamada PowerShell: câmeras + endpoints de captura presentes."""
    script = r"""
$cams = New-Object System.Collections.Generic.List[string]
$mics = New-Object System.Collections.Generic.List[string]
Get-PnpDevice -PresentOnly -Status OK | ForEach-Object {
  $class = $_.Class
  $name = $_.FriendlyName
  if (-not $name) { return }
  if ($class -eq 'Camera' -or $class -eq 'Image') {
    $cams.Add($name)
    return
  }
  if ($class -ne 'AudioEndpoint') { return }
  $l = $name.ToLowerInvariant()
  if ($l -match 'speaker|headphone|fones de ouvido|alto-falante|output|render|hdmi|digitaloutput|digital output') { return }
  if ($l -match 'virtual|broadcast|stereo mix|what u hear|what you hear') { return }
  if ($l -match 'microfone|microphone|\bmic\b|line[- ]?in|entrada de linha|\bentrada\b|headset') {
    $mics.Add($name)
  }
}
@{ cams = $cams; mics = $mics } | ConvertTo-Json -Compress
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired):
        return [], []

    raw = (result.stdout or "").strip()
    if not raw:
        return [], []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [], []

    cam_names = _as_str_list(data.get("cams"))
    mic_names = _as_str_list(data.get("mics"))

    cameras = _unique_devices(
        [DeviceInfo(label=n, value=n) for n in cam_names]
    )
    mics = _unique_devices(
        [DeviceInfo(label=n, value=n) for n in mic_names]
    )
    return cameras, mics


def _as_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _unique_devices(devices: list[DeviceInfo]) -> list[DeviceInfo]:
    seen: set[str] = set()
    unique: list[DeviceInfo] = []
    for device in devices:
        if device.value in seen:
            continue
        seen.add(device.value)
        unique.append(device)
    return unique
