"""Saúde do Raspberry Pi: subtensão e limitação por temperatura (vcgencmd get_throttled)."""

from __future__ import annotations

import shutil
import subprocess

_UNDERVOLT_NOW = 1 << 0
_THROTTLED_NOW = 1 << 2
_UNDERVOLT_BOOT = 1 << 16
_THROTTLED_BOOT = (1 << 18) | (1 << 19)


def throttled_flags() -> int | None:
    """Bits do `vcgencmd get_throttled` (None fora do Pi ou se falhar)."""
    if shutil.which("vcgencmd") is None:
        return None
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return int((result.stdout or "").strip().split("=", 1)[1], 16)
    except (OSError, subprocess.TimeoutExpired, IndexError, ValueError):
        return None


def power_warnings(flags: int | None = None) -> list[str]:
    """Avisos em português sobre energia/temperatura que derrubam câmera e mic USB."""
    if flags is None:
        flags = throttled_flags()
    if not flags:
        return []
    warnings: list[str] = []
    if flags & (_UNDERVOLT_NOW | _UNDERVOLT_BOOT):
        when = "agora" if flags & _UNDERVOLT_NOW else "desde o boot"
        warnings.append(
            f"⚠ Subtensão detectada ({when}): a fonte não aguenta Pi + câmera + mic e o USB "
            "desconecta. Use a fonte oficial (Pi 4: 5V/3A · Pi 5: 5V/5A) ou um hub USB com fonte."
        )
    if flags & (_THROTTLED_NOW | _THROTTLED_BOOT):
        warnings.append(
            "⚠ CPU limitada por temperatura: use dissipador/cooler ou reduza resolução/FPS."
        )
    return warnings
