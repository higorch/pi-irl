"""Cliente BSBF (bonding): status e start opcional antes da transmissão."""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass


# Units comuns do BSBF no Linux
_CANDIDATE_UNITS = ("bsbf-mptcp", "bsbf-bonding", "bsbf")


@dataclass(frozen=True)
class BondingStatus:
    installed: bool
    active: bool
    unit: str
    detail: str

    @property
    def label_pt(self) -> str:
        if not self.installed:
            return "não instalado"
        if self.active:
            return "ativo"
        return "parado"


def bonding_status() -> BondingStatus:
    """Estado atual do serviço BSBF (somente Linux)."""
    if platform.system() != "Linux":
        return BondingStatus(
            installed=False,
            active=False,
            unit="",
            detail="Bonding disponível no Raspberry Pi / Linux.",
        )

    if shutil.which("systemctl") is None:
        return BondingStatus(
            installed=False,
            active=False,
            unit="",
            detail="systemctl não encontrado.",
        )

    unit = _find_unit()
    if not unit:
        return BondingStatus(
            installed=False,
            active=False,
            unit="",
            detail="Cliente BSBF não encontrado neste sistema.",
        )

    active = _is_active(unit)
    return BondingStatus(
        installed=True,
        active=active,
        unit=unit,
        detail=f"serviço {unit}",
    )


def ensure_bonding_started() -> tuple[bool, str]:
    """
    Tenta iniciar o BSBF se instalado.

    Nunca bloqueia a transmissão: retorna (ok, mensagem amigável).
    """
    status = bonding_status()
    if not status.installed:
        return False, "Bonding: cliente BSBF não instalado — transmitindo sem agregação."

    if status.active:
        return True, f"Bonding: ativo ({status.unit})."

    if _start_unit(status.unit):
        # recheck curto
        if _is_active(status.unit):
            return True, f"Bonding: iniciado ({status.unit})."
        return False, (
            f"Bonding: pedido de start enviado ({status.unit}), "
            "mas o serviço ainda não está ativo — transmitindo mesmo assim."
        )

    return False, (
        f"Bonding: falha ao iniciar {status.unit} — "
        "transmitindo sem agregação."
    )


def _find_unit() -> str:
    for unit in _CANDIDATE_UNITS:
        try:
            result = subprocess.run(
                ["systemctl", "list-unit-files", f"{unit}.service"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            text = (result.stdout or "") + (result.stderr or "")
            if unit in text and "0 unit files listed" not in text:
                return unit
        except (OSError, subprocess.TimeoutExpired):
            continue

    # Fallback: binário presente
    if shutil.which("bsbf-bonding") or shutil.which("bsbf-mptcp"):
        return _CANDIDATE_UNITS[0]
    return ""


def _is_active(unit: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return (result.stdout or "").strip() == "active"
    except (OSError, subprocess.TimeoutExpired):
        return False


def _start_unit(unit: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "start", unit],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
