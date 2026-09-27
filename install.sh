#!/usr/bin/env bash
# Instala dependências do Pi-IRL no Raspberry Pi / Linux.
# Uso:
#   chmod +x install.sh
#   ./install.sh
#   ./install.sh --with-bsbf --server IP --port 16384 --uuid UUID

set -euo pipefail
cd "$(dirname "$0")"

WITH_BSBF=0
BSBF_SERVER=""
BSBF_PORT=""
BSBF_UUID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-bsbf) WITH_BSBF=1; shift ;;
    --server) BSBF_SERVER="${2:-}"; shift 2 ;;
    --port) BSBF_PORT="${2:-}"; shift 2 ;;
    --uuid) BSBF_UUID="${2:-}"; shift 2 ;;
    -h|--help)
      echo "Uso: ./install.sh [--with-bsbf --server IP --port PORTA --uuid UUID]"
      exit 0
      ;;
    *)
      echo "Argumento desconhecido: $1"
      exit 1
      ;;
  esac
done

echo "==> Pacotes do sistema (FFmpeg, V4L2, ALSA, Python)"
sudo apt-get update
sudo apt-get install -y \
  ffmpeg \
  v4l-utils \
  alsa-utils \
  python3 \
  python3-venv \
  python3-pip \
  git \
  curl

echo "==> Ambiente Python (.venv)"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "==> Criado .env a partir de .env.example — edite VPS_HOST antes de transmitir"
fi

chmod +x start-pi-irl.sh install-desktop-shortcut.sh 2>/dev/null || true
if [[ -x ./install-desktop-shortcut.sh ]]; then
  ./install-desktop-shortcut.sh || true
fi

if [[ "$WITH_BSBF" -eq 1 ]]; then
  if [[ -z "$BSBF_SERVER" || -z "$BSBF_PORT" || -z "$BSBF_UUID" ]]; then
    echo "BSBF: informe --server, --port e --uuid"
    exit 1
  fi
  echo "==> Instalando cliente BSBF"
  curl -fsSL cld.bondingshouldbefree.org | sudo sh -s -- \
    --server-ipv4 "$BSBF_SERVER" \
    --server-port "$BSBF_PORT" \
    --uuid "$BSBF_UUID"
  echo "BSBF instalado. Preencha os mesmos dados no card Bonding da aba Conexões do app."
else
  echo "==> BSBF omitido (opcional). Para instalar:"
  echo "  ./install.sh --with-bsbf --server IP --port PORTA --uuid UUID"
fi

echo
echo "Pronto. Inicie com: ./start-pi-irl.sh"
echo "ou: source .venv/bin/activate && python -m app.main"
