#!/usr/bin/env bash
# Instala dependências do Pi-IRL no Raspberry Pi / Linux.
# Uso:
#   chmod +x install.sh
#   ./install.sh
#   ./install.sh --with-bsbf --server IP --port 16384 --uuid UUID
#   ./install.sh --no-autostart --no-camera-fix --no-reboot

set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

WITH_BSBF=0
CAMERA_FIX=1
AUTO_REBOOT=1
AUTOSTART=1
NEED_REBOOT=0
UVC_OPTIONS="options uvcvideo quirks=0x180 nodrop=1 timeout=5000"
BSBF_SERVER=""
BSBF_PORT=""
BSBF_UUID=""

usage() {
  cat <<'EOF'
Uso: ./install.sh [opções]
  --with-bsbf          Instala o cliente BSBF agora (requer --server --port --uuid)
  --server IP          IPv4 do servidor BSBF
  --port PORTA         Porta do cliente BSBF
  --uuid UUID          UUID do cliente BSBF
  --no-autostart       Não inicia o Pi-IRL (nem a transmissão) ao ligar o Pi
  --no-camera-fix      Não aplica o ajuste UVC / USB autosuspend da câmera
  --no-reboot          Não reinicia sozinho após o ajuste da câmera
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-bsbf) WITH_BSBF=1; shift ;;
    --server) BSBF_SERVER="${2:-}"; shift 2 ;;
    --port) BSBF_PORT="${2:-}"; shift 2 ;;
    --uuid) BSBF_UUID="${2:-}"; shift 2 ;;
    --camera-fix) CAMERA_FIX=1; shift ;;
    --no-camera-fix) CAMERA_FIX=0; shift ;;
    --no-reboot) AUTO_REBOOT=0; shift ;;
    --no-autostart) AUTOSTART=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Argumento desconhecido: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Rode como usuário normal (sem sudo): ./install.sh"
  exit 1
fi

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

AUTOSTART_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/pi-irl.desktop"
if [[ "$AUTOSTART" -eq 1 ]]; then
  echo "==> Início automático ao ligar o Pi"
  mkdir -p "$(dirname "$AUTOSTART_FILE")"
  cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Pi-IRL
Comment=Abre o Pi-IRL e inicia a transmissão se a configuração estiver completa
Exec=$ROOT/start-pi-irl.sh --autostart
Path=$ROOT
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
  echo "Autostart: $AUTOSTART_FILE"
else
  rm -f "$AUTOSTART_FILE"
  echo "==> Início automático desativado"
fi

if [[ "$CAMERA_FIX" -eq 1 ]]; then
  echo "==> Câmera UVC: quirks + USB autosuspend desativado"
  CAMERA_CHANGED=0

  UVC_CONF=/etc/modprobe.d/uvcvideo.conf
  if [[ -f "$UVC_CONF" ]] && grep -qxF "$UVC_OPTIONS" "$UVC_CONF"; then
    echo "$UVC_CONF já configurado"
  else
    echo "$UVC_OPTIONS" | sudo tee "$UVC_CONF" >/dev/null
    echo "Gravado $UVC_CONF"
    CAMERA_CHANGED=1
  fi

  CMDLINE=/boot/firmware/cmdline.txt
  [[ -f "$CMDLINE" ]] || CMDLINE=/boot/cmdline.txt
  if [[ -f "$CMDLINE" ]]; then
    if grep -q 'usbcore.autosuspend=-1' "$CMDLINE"; then
      echo "$CMDLINE já tem usbcore.autosuspend=-1"
    else
      [[ -f "$CMDLINE.bak-pi-irl" ]] || sudo cp "$CMDLINE" "$CMDLINE.bak-pi-irl"
      # cmdline.txt deve continuar em uma única linha
      sudo sed -i '1 s/[[:space:]]*$/ usbcore.autosuspend=-1/' "$CMDLINE"
      echo "Adicionado usbcore.autosuspend=-1 em $CMDLINE (backup: $CMDLINE.bak-pi-irl)"
      CAMERA_CHANGED=1
    fi
  else
    echo "cmdline.txt não encontrado — adicione usbcore.autosuspend=-1 manualmente."
  fi

  if [[ "$CAMERA_CHANGED" -eq 1 ]]; then
    if command -v update-initramfs >/dev/null 2>&1; then
      sudo update-initramfs -u
    fi
    NEED_REBOOT=1
  fi
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
  echo "==> BSBF: o app instala o cliente sozinho ao iniciar a transmissão"
  echo "    se servidor, porta e UUID estiverem preenchidos no card Bonding."
fi

# -k ignora a senha em cache do apt acima, para testar como o app vai rodar
if ! sudo -k -n true 2>/dev/null; then
  echo
  echo "AVISO: sudo pede senha para $USER. O app precisa de sudo sem senha para"
  echo "instalar/ativar o BSBF sozinho. Veja 'Sudo sem senha' no README."
fi

echo
echo "Pronto. Inicie com: ./start-pi-irl.sh"
echo "ou: source .venv/bin/activate && python -m app.main"
if [[ "$NEED_REBOOT" -eq 1 ]]; then
  echo
  if [[ "$AUTO_REBOOT" -eq 1 ]]; then
    echo "Reiniciando em 10 s para aplicar o ajuste da câmera (Ctrl+C cancela)…"
    sleep 10
    sudo reboot
  else
    echo "Reinicie para aplicar o ajuste da câmera: sudo reboot"
  fi
fi
