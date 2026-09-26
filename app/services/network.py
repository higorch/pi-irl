"""Lista leve das conexões de rede do Pi (Wi‑Fi, 4G, ethernet)."""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkLink:
    """Uma interface de rede com estado resumido."""

    iface: str
    kind: str  # wifi | ethernet | cellular | other
    label: str
    ipv4: str
    up: bool
    has_default_route: bool
    detail: str = ""

    @property
    def summary(self) -> str:
        status = "conectado" if self.up and self.ipv4 else "sem IP"
        if self.up and self.ipv4 and not self.has_default_route:
            status = "sem rota"
        ip = self.ipv4 or "—"
        extra = f" · {self.detail}" if self.detail else ""
        mark = "●" if self.up and self.ipv4 else "○"
        return f"{mark} {self.label} ({self.iface})  {ip}  {status}{extra}"


def _should_skip(iface: str) -> bool:
    lower = iface.lower()
    if lower == "lo":
        return True
    return any(
        lower.startswith(prefix)
        for prefix in ("docker", "br-", "veth", "virbr", "tun", "tap", "wg", "vmnet")
    )


def list_network_links() -> list[NetworkLink]:
    """Varredura rápida; no Windows retorna lista vazia (alvo = Pi/Linux)."""
    if platform.system() != "Linux":
        return []

    addrs = _ip_addr_map()
    routes = _default_route_ifaces()
    links: list[NetworkLink] = []

    for iface, (up, ipv4) in addrs.items():
        if _should_skip(iface):
            continue
        kind, label = _classify_iface(iface)
        detail = ""
        if kind == "wifi" and up:
            detail = _wifi_ssid(iface)
        links.append(
            NetworkLink(
                iface=iface,
                kind=kind,
                label=label,
                ipv4=ipv4,
                up=up,
                has_default_route=iface in routes,
                detail=detail,
            )
        )

    links.sort(key=lambda item: (not (item.up and item.ipv4), item.label, item.iface))
    return links


def _classify_iface(iface: str) -> tuple[str, str]:
    lower = iface.lower()
    if lower.startswith(("wlan", "wl")):
        return "wifi", "Wi‑Fi"
    if lower.startswith(("wwan", "ww", "usb", "ppp", "cdc")):
        return "cellular", "4G / LTE"
    if lower.startswith(("eth", "en")):
        return "ethernet", "Ethernet"
    return "other", iface


def _ip_addr_map() -> dict[str, tuple[bool, str]]:
    """iface -> (up, ipv4)."""
    try:
        result = subprocess.run(
            ["ip", "-br", "addr"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        output = result.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        return {}

    mapping: dict[str, tuple[bool, str]] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        iface = parts[0].split("@", 1)[0]
        state = parts[1].upper()
        up = state in {"UP", "UNKNOWN"}
        ipv4 = ""
        for token in parts[2:]:
            if re.match(r"^\d+\.\d+\.\d+\.\d+", token):
                ipv4 = token.split("/", 1)[0]
                break
        mapping[iface] = (up, ipv4)
    return mapping


def _default_route_ifaces() -> set[str]:
    try:
        result = subprocess.run(
            ["ip", "-4", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        output = result.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        return set()

    found: set[str] = set()
    for line in output.splitlines():
        match = re.search(r"\bdev\s+(\S+)", line)
        if match:
            found.add(match.group(1))
    return found


def _wifi_ssid(iface: str) -> str:
    try:
        result = subprocess.run(
            ["iwgetid", iface, "-r"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        ssid = (result.stdout or "").strip()
        return ssid
    except (OSError, subprocess.TimeoutExpired):
        return ""
