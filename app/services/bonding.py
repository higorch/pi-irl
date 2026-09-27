"""Cliente BSBF (bondingshouldbefree): status, instalação e ativação antes da transmissão.

Referência: https://github.com/bondingshouldbefree
- Instalar/reconfigurar: curl -fsSL cld.bondingshouldbefree.org | sudo sh -s -- \
      --server-ipv4 IP --server-port PORTA --uuid UUID
- Config instalada: /usr/local/etc/bsbf/bsbf-bonding.conf
- Ativar: bsbf-bonding --enable (sobe bsbf-mptcp + xray-bsbf-bonding)

Com o bonding ativo, TCP e UDP para IPs públicos passam pelo túnel (tproxy do xray),
então o SRT do FFmpeg é agregado sem mudar a URL.
"""

from __future__ import annotations

import ipaddress
import os
import platform
import shutil
import subprocess
import uuid as uuid_lib
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from app.config import SUDO_PASSWORD_ENV, sudo_password

BSBF_BIN_DEFAULT = "/usr/local/sbin/bsbf-bonding"
BSBF_CONF = "/usr/local/etc/bsbf/bsbf-bonding.conf"
BSBF_UNITS = ("bsbf-mptcp", "xray-bsbf-bonding")
CLIENT_INSTALLER_URL = "cld.bondingshouldbefree.org"

INSTALL_TIMEOUT_MS = 20 * 60 * 1000
ENABLE_TIMEOUT_MS = 90 * 1000

# Helper do `sudo -A`: lê a senha do ambiente do próprio sudo (nunca vai para argv nem disco).
_ASKPASS_VAR = "PI_IRL_SUDO_ASKPASS_SECRET"
_ASKPASS_SCRIPT = f"#!/bin/sh\nprintf '%s\\n' \"${_ASKPASS_VAR}\"\n"


@dataclass(frozen=True)
class BondingStatus:
    installed: bool
    active: bool
    detail: str
    conf_known: bool = False
    server: str = ""
    port: int = 0
    uuid: str = ""

    @property
    def label_pt(self) -> str:
        if not self.installed:
            return "não instalado"
        return "ativo" if self.active else "parado"

    def matches(self, server: str, port: int, uuid: str) -> bool:
        return (
            self.conf_known
            and self.server == server.strip()
            and self.port == int(port)
            and self.uuid.lower() == uuid.strip().lower()
        )


def is_supported() -> bool:
    return platform.system() == "Linux"


def validate_settings(server: str, port: int, uuid: str) -> str | None:
    """Erro amigável se os dados do BSBF forem inválidos (None = ok)."""
    try:
        ipaddress.IPv4Address(server.strip())
    except ValueError:
        return "o servidor BSBF deve ser um endereço IPv4 (ex.: 203.0.113.10)"
    if not 1 <= int(port) <= 65535:
        return "porta BSBF inválida"
    try:
        uuid_lib.UUID(uuid.strip())
    except ValueError:
        return "UUID do cliente BSBF inválido"
    return None


def bonding_bin() -> str:
    return shutil.which("bsbf-bonding") or BSBF_BIN_DEFAULT


def bonding_status() -> BondingStatus:
    """Estado atual do cliente BSBF (leve: 1 chamada ao systemctl)."""
    if not is_supported():
        return BondingStatus(
            installed=False,
            active=False,
            detail="Bonding disponível no Raspberry Pi / Linux.",
        )

    if not os.path.isfile(bonding_bin()):
        return BondingStatus(
            installed=False,
            active=False,
            detail="Cliente BSBF não encontrado neste sistema.",
        )

    conf = _read_installed_conf()
    return BondingStatus(
        installed=True,
        active=_units_active(),
        detail="",
        conf_known=conf is not None,
        server=(conf or {}).get("server_ipv4", ""),
        port=_to_int((conf or {}).get("server_port", "")),
        uuid=(conf or {}).get("uuid", ""),
    )


class BondingManager(QObject):
    """Prepara o BSBF de forma assíncrona: instala, reconfigura ou só ativa."""

    log_line = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._action = ""
        self._target = ("", 0, "")
        self._tail: list[str] = []
        self._buffer = ""

    @property
    def busy(self) -> bool:
        return self._process is not None

    def prepare(self, server: str, port: int, uuid: str) -> None:
        if self.busy:
            return

        server, uuid = server.strip(), uuid.strip()
        if not is_supported():
            self._finish_later(
                False,
                "Bonding: disponível só no Raspberry Pi / Linux — transmitindo sem agregação.",
            )
            return

        error = validate_settings(server, port, uuid)
        if error:
            self._finish_later(False, f"Bonding: {error} — transmitindo sem agregação.")
            return

        self._target = (server, int(port), uuid)
        status = bonding_status()

        if not status.installed:
            if shutil.which("curl") is None:
                self._finish_later(
                    False,
                    "Bonding: curl não encontrado para instalar o cliente BSBF — "
                    "transmitindo sem agregação.",
                )
                return
            self.log_line.emit(
                "Bonding: instalando cliente BSBF (pode levar alguns minutos)…"
            )
            script = (
                'tmp=$(mktemp) && curl -fsSL "$0" -o "$tmp" && '
                'sh "$tmp" --server-ipv4 "$1" --server-port "$2" --uuid "$3"; '
                'rc=$?; rm -f "$tmp"; exit $rc'
            )
            self._run(
                "instalar o cliente BSBF",
                ["sh", "-c", script, CLIENT_INSTALLER_URL, server, str(port), uuid],
                INSTALL_TIMEOUT_MS,
            )
            return

        if status.conf_known and not status.matches(server, port, uuid):
            self.log_line.emit(f"Bonding: aplicando servidor {server}:{port}…")
            script = (
                "mkdir -p /usr/local/etc/bsbf && "
                'printf "server_ipv4=%s\\nserver_port=%s\\nuuid=%s\\n" "$1" "$2" "$3" '
                f"> {BSBF_CONF} && "
                '"$4" --enable'
            )
            self._run(
                "aplicar a configuração do BSBF",
                ["sh", "-c", script, "sh", server, str(port), uuid, bonding_bin()],
                ENABLE_TIMEOUT_MS,
            )
            return

        if not status.active:
            self.log_line.emit("Bonding: iniciando cliente BSBF…")
            self._run("iniciar o cliente BSBF", [bonding_bin(), "--enable"], ENABLE_TIMEOUT_MS)
            return

        self._finish_later(True, f"Bonding: ativo ({server}:{port}).")

    def _run(self, action: str, argv: list[str], timeout_ms: int) -> None:
        process = QProcess(self)
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            password = sudo_password()
            askpass = _askpass_helper() if password else None
            if askpass:
                env = QProcessEnvironment.systemEnvironment()
                env.insert("SUDO_ASKPASS", askpass)
                env.insert(_ASKPASS_VAR, password)
                process.setProcessEnvironment(env)
                argv = ["sudo", "-A", *argv]
            else:
                argv = ["sudo", "-n", *argv]

        self._action = action
        self._tail = []
        self._buffer = ""
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._on_output)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)
        self._process = process
        self._timer.start(timeout_ms)
        process.start(argv[0], argv[1:])

    def _on_output(self) -> None:
        if self._process is None:
            return
        chunk = bytes(self._process.readAllStandardOutput()).decode("utf-8", "replace")
        self._buffer += chunk
        *lines, self._buffer = self._buffer.split("\n")
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            self._tail = (self._tail + [line])[-5:]
            if line.startswith(("Installing", "Configuring", "Enabling", "Installation")):
                self.log_line.emit(f"Bonding: {line}")

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if self._process is None:
            return
        self._on_output()
        self._cleanup()

        server, port, _uuid = self._target
        output = "\n".join(self._tail).lower()
        if exit_code != 0:
            if "incorrect password" in output or "incorreta" in output:
                self.finished.emit(
                    False,
                    f"Bonding: senha do sudo incorreta — confira {SUDO_PASSWORD_ENV} no .env. "
                    "Transmitindo sem agregação.",
                )
                return
            if "password is required" in output or "senha" in output:
                self.finished.emit(
                    False,
                    f"Bonding: o sudo pediu senha — defina {SUDO_PASSWORD_ENV} no .env "
                    "ou libere sudo sem senha (veja o README). Transmitindo sem agregação.",
                )
                return
            last = self._tail[-1] if self._tail else ""
            detail = f": {last[:120]}" if last else ""
            self.finished.emit(
                False,
                f"Bonding: falha ao {self._action} (código {exit_code}){detail} — "
                "transmitindo sem agregação.",
            )
            return

        if _units_active():
            self.finished.emit(True, f"Bonding: ativo ({server}:{port}).")
        else:
            self.finished.emit(
                False,
                "Bonding: comando executado, mas os serviços do BSBF não ficaram ativos — "
                "transmitindo sem agregação.",
            )

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error != QProcess.ProcessError.FailedToStart or self._process is None:
            return
        self._cleanup()
        self.finished.emit(
            False,
            f"Bonding: não foi possível {self._action} (sudo indisponível?) — "
            "transmitindo sem agregação.",
        )

    def _on_timeout(self) -> None:
        if self._process is None:
            return
        process = self._process
        self._cleanup()
        process.kill()
        self.finished.emit(
            False,
            f"Bonding: tempo esgotado ao {self._action} — transmitindo sem agregação.",
        )

    def _cleanup(self) -> None:
        self._timer.stop()
        process, self._process = self._process, None
        if process is not None:
            process.deleteLater()

    def _finish_later(self, ok: bool, message: str) -> None:
        QTimer.singleShot(0, lambda: self.finished.emit(ok, message))


def _askpass_helper() -> str | None:
    """Caminho do helper do `sudo -A` (0700 em ~/.cache/pi-irl). None se não der para criar."""
    path = Path.home() / ".cache" / "pi-irl" / "sudo-askpass.sh"
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not path.is_file() or path.read_text(encoding="utf-8") != _ASKPASS_SCRIPT:
            path.write_text(_ASKPASS_SCRIPT, encoding="utf-8")
        os.chmod(path, 0o700)
    except OSError:
        return None
    return str(path)


def _units_active() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", *BSBF_UNITS],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    states = (result.stdout or "").split()
    return len(states) == len(BSBF_UNITS) and all(s == "active" for s in states)


def _read_installed_conf() -> dict[str, str] | None:
    try:
        with open(BSBF_CONF, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return None
    values: dict[str, str] = {}
    for raw in text.splitlines():
        key, sep, value = raw.strip().partition("=")
        if sep:
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _to_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
