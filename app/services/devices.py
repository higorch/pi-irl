"""Detecção rápida de câmeras USB e microfones USB ou P2."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeviceInfo:
    """Fonte de captura: nome amigável + valor interno do FFmpeg."""

    label: str
    value: str


# Cache curto: evita 2+ varreduras ao abrir a UI / refresh.
_CACHE_TTL_S = 4.0
_cache_at = 0.0
_cache_cameras: list[DeviceInfo] = []
_cache_mics: list[DeviceInfo] = []


def list_cameras() -> list[DeviceInfo]:
    """Câmeras locais conectadas (USB, CSI, etc.)."""
    cameras, _ = _list_all_cached()
    return cameras


def list_microphones() -> list[DeviceInfo]:
    """Microfones locais conectados (USB ou entrada P2)."""
    _, mics = _list_all_cached()
    return mics


def invalidate_cache() -> None:
    """Força nova varredura na próxima listagem (dispositivo conectado/removido)."""
    global _cache_at
    _cache_at = 0.0


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


_ALSA_HW_RE = re.compile(r"^(?:plug)?hw:(\d+)(?:,(\d+))?$")


def stable_value(value: str) -> str:
    """Converte /dev/videoN e hw:N,M (mudam ao reconectar o USB) para nomes estáveis.

    Câmera → /dev/v4l/by-id/…  ·  Microfone → hw:CARD=<id>,DEV=M. Sem equivalente: devolve igual.
    """
    text = (value or "").strip()
    if platform.system() != "Linux" or not text:
        return text
    if re.fullmatch(r"/dev/video\d+", text):
        return _v4l2_stable_path(text)
    match = _ALSA_HW_RE.match(text)
    if match:
        card_id = _alsa_card_id(match.group(1))
        if card_id:
            return f"hw:CARD={card_id},DEV={match.group(2) or 0}"
    return text


def _v4l2_stable_path(path: str) -> str:
    """Link de /dev/v4l/by-id (ou by-path) que aponta para o /dev/videoN."""
    try:
        target = os.path.realpath(path)
    except OSError:
        return path
    for folder in ("/dev/v4l/by-id", "/dev/v4l/by-path"):
        try:
            links = sorted(Path(folder).iterdir(), key=lambda p: ("index0" not in p.name, p.name))
        except OSError:
            continue
        for link in links:
            try:
                if os.path.realpath(link) == target:
                    return str(link)
            except OSError:
                continue
    return path


def _alsa_card_id(card: str) -> str:
    try:
        return Path(f"/proc/asound/card{card}/id").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _sysfs_is_usb(device_link: Path) -> bool:
    """True se o link `device` do sysfs aponta para um dispositivo no barramento USB."""
    try:
        return "/usb" in os.path.realpath(device_link)
    except OSError:
        return False


def _is_usb_video(path: str) -> bool:
    return _sysfs_is_usb(Path("/sys/class/video4linux") / Path(path).name / "device")


def _is_usb_sound_card(card: str) -> bool:
    return Path(f"/proc/asound/card{card}/usbid").exists() or _sysfs_is_usb(
        Path(f"/sys/class/sound/card{card}/device")
    )


def _list_linux_cameras() -> list[DeviceInfo]:
    """Câmeras V4L2 ligadas via USB (ignora CSI e nós internos do Pi como codec/ISP)."""
    devices: list[DeviceInfo] = []
    # Um único comando: agrupa nós por dispositivo físico; o 1º /dev/video* costuma ser captura.
    grouped = _v4l2_list_devices_groups()
    if grouped:
        for name, paths in grouped:
            paths = [p for p in paths if _is_usb_video(p)]
            if not paths:
                continue
            path = _pick_v4l2_capture_path(paths)
            if not path:
                continue
            # "SJCAM SJ4000 (usb-xhci-hcd.0-1)" → "SJCAM SJ4000"
            label = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip() or path
            devices.append(DeviceInfo(label=label, value=_v4l2_stable_path(path)))
        return _unique_devices(devices)

    # Fallback sem v4l2-ctl --list-devices
    video_root = Path("/dev")
    if not video_root.exists():
        return devices

    for path in sorted(video_root.glob("video*")):
        if not path.exists() or not _is_usb_video(str(path)):
            continue
        name = _v4l2_sysfs_name(path)
        if _looks_like_metadata_node(name):
            continue
        if not _is_v4l2_video_capture_fast(path):
            continue
        label = name or str(path)
        devices.append(DeviceInfo(label=label, value=_v4l2_stable_path(str(path))))

    return _unique_devices(devices)


def _pick_v4l2_capture_path(paths: list[str]) -> str | None:
    """Escolhe o primeiro nó V4L2 que realmente captura vídeo."""
    fallback = ""
    for path in paths:
        name = _v4l2_sysfs_name(Path(path))
        if _looks_like_metadata_node(name):
            continue
        if not fallback:
            fallback = path
        if _is_v4l2_video_capture_fast(Path(path)):
            return path
    return fallback or None


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


_VIRTUAL_SOUND_CARD = re.compile(r"loopback|dummy|null|virtual|hdmi", re.IGNORECASE)


def _mic_label(name: str, *, usb: bool) -> str:
    return f"{name} · {'USB' if usb else 'P2'}"


def _list_linux_microphones() -> list[DeviceInfo]:
    """Entradas de captura ALSA: placas USB e entradas analógicas P2 (codec/HAT), sem virtuais."""
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
        r"card\s+(\d+):([^\n]*?)device\s+(\d+):\s*([^\n]+)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(output):
        card, card_desc = match.group(1), match.group(2)
        device, name = match.group(3), match.group(4).strip()
        usb = _is_usb_sound_card(card)
        if not usb and _VIRTUAL_SOUND_CARD.search(f"{card_desc} {name}"):
            continue
        value = stable_value(f"hw:{card},{device}")
        # arecord: "USB Audio [USB Audio]" → nome limpo
        label = re.sub(r"\s*\[[^\]]*\]\s*$", "", name).strip() or value
        devices.append(DeviceInfo(label=_mic_label(label, usb=usb), value=value))

    return _unique_devices(devices)


def _list_windows_all() -> tuple[list[DeviceInfo], list[DeviceInfo]]:
    """Uma chamada PowerShell: câmeras USB e microfones USB ou P2.

    Câmera: InstanceId USB\\…  ·  Microfone (endpoint SWD\\MMDEVAPI): pai USB\\…
    (USB) ou HDAUDIO\\/INTELAUDIO\\… (entrada P2 da placa-mãe); ROOT\\… = virtual, ignorado.
    """
    script = r"""
$all = @(Get-PnpDevice -PresentOnly)
$camDevs = New-Object System.Collections.Generic.List[object]
$micDevs = New-Object System.Collections.Generic.List[object]
foreach ($d in $all) {
  $name = $d.FriendlyName
  if ($d.Status -ne 'OK' -or -not $name) { continue }
  if ($d.Class -eq 'Camera' -or $d.Class -eq 'Image') {
    if ($d.InstanceId -like 'USB\*') { $camDevs.Add($d) }
    continue
  }
  if ($d.Class -ne 'AudioEndpoint') { continue }
  $l = $name.ToLowerInvariant()
  if ($l -match 'speaker|headphone|fones de ouvido|fone de ouvido|alto-falante|output|render|hdmi|digitaloutput|digital output') { continue }
  if ($l -match 'virtual|broadcast|stereo mix|what u hear|what you hear') { continue }
  if ($l -match 'microfone|microphone|\bmic\b|line[- ]?in|entrada de linha|\bentrada\b|headset') { $micDevs.Add($d) }
}
$parent = @{}
if ($micDevs.Count) {
  $micDevs | Get-PnpDeviceProperty -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue |
    ForEach-Object { $parent[$_.InstanceId] = [string]$_.Data }
}
$mics = @()
foreach ($d in $micDevs) {
  $p = $parent[$d.InstanceId]
  $kind = if ($p -like 'USB\*') { 'usb' } elseif ($p -like 'HDAUDIO\*' -or $p -like 'INTELAUDIO\*') { 'p2' } else { '' }
  if ($kind) { $mics += [pscustomobject]@{ name = [string]$d.FriendlyName; kind = $kind } }
}
$cams = @($camDevs | ForEach-Object { [string]$_.FriendlyName })
[pscustomobject]@{ cams = $cams; mics = $mics } | ConvertTo-Json -Compress -Depth 3
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=15,
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
    raw_mics = data.get("mics") or []
    if isinstance(raw_mics, dict):
        raw_mics = [raw_mics]

    cameras = _unique_devices(
        [DeviceInfo(label=n, value=n) for n in cam_names]
    )
    mics: list[DeviceInfo] = []
    for item in raw_mics:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            mics.append(DeviceInfo(label=_mic_label(name, usb=item.get("kind") == "usb"), value=name))
    return cameras, _unique_devices(mics)


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
