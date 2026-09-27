#!/usr/bin/env bash
# Instala dependências do Pi-IRL no Raspberry Pi / Linux.
# Antes: cp .env.example .env && nano .env   (o install confere e para se faltar algo)
# Uso:
#   chmod +x install.sh
#   ./install.sh
#   ./install.sh --with-bsbf        # usa BONDING_* do .env (ou --server IP --port P --uuid U)
#   ./install.sh --no-autostart --no-camera-fix --no-reboot

set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

WITH_BSBF=0
CAMERA_FIX=1
AUTO_REBOOT=1
AUTOSTART=1
UVC_OPTIONS="options uvcvideo quirks=0x180 nodrop=1 timeout=5000"
BSBF_SERVER=""
BSBF_PORT=""
BSBF_UUID=""

usage() {
  cat <<'EOF'
Uso: ./install.sh [opções]   (configure o .env antes: cp .env.example .env && nano .env)
  --with-bsbf          Instala o cliente BSBF agora (dados do BONDING_* do .env)
  --server IP          IPv4 do servidor BSBF (sobrescreve BONDING_SERVER)
  --port PORTA         Porta do cliente BSBF (sobrescreve BONDING_PORT)
  --uuid UUID          UUID do cliente BSBF (sobrescreve BONDING_UUID)
  --no-autostart       Não inicia o Pi-IRL (nem a transmissão) ao ligar o Pi
  --no-camera-fix      Não aplica o ajuste UVC / USB autosuspend da câmera
  --no-reboot          Não reinicia sozinho ao final da instalação
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

if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  echo "==> Criado .env a partir de .env.example."
  echo "    Configure o .env antes de instalar (VPS_HOST, SRT_PORT, STREAM_ID e, se usar,"
  echo "    BONDING_* e PI_SUDO_PASSWORD):"
  echo "      nano .env"
  echo "    Depois rode de novo: ./install.sh"
  exit 1
fi
# .env pode guardar a senha do sudo
chmod 600 .env

# Valor de uma chave do .env (sem executar o arquivo): aspas e espaços/CR nas pontas removidos
env_value() {
  [[ -f .env ]] || return 0
  local value
  value="$(grep -E "^[[:space:]]*$1[[:space:]]*=" .env | tail -n 1 || true)"
  value="${value#*=}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  value="${value#[\"\']}"
  value="${value%[\"\']}"
  printf '%s' "$value"
}

echo "==> Conferindo o .env"
ENV_ERRORS=()
is_port() { [[ "$1" =~ ^[0-9]+$ ]] && (( 10#$1 >= 1 && 10#$1 <= 65535 )); }

VPS_HOST_V="$(env_value VPS_HOST)"
if [[ -z "$VPS_HOST_V" || "$VPS_HOST_V" == "IP_OU_DOMINIO_DA_VPS" ]]; then
  ENV_ERRORS+=("VPS_HOST: informe o IP ou domínio da VPS (MediaMTX)")
fi
is_port "$(env_value SRT_PORT)" || ENV_ERRORS+=("SRT_PORT: porta inválida (padrão 8890)")
[[ -n "$(env_value STREAM_ID)" ]] || ENV_ERRORS+=("STREAM_ID: informe o path do stream (padrão irl)")

ENV_BONDING_SERVER="$(env_value BONDING_SERVER)"
ENV_BONDING_PORT="$(env_value BONDING_PORT)"
ENV_BONDING_UUID="$(env_value BONDING_UUID)"
if [[ -n "$ENV_BONDING_SERVER$ENV_BONDING_PORT$ENV_BONDING_UUID" ]]; then
  if [[ -z "$ENV_BONDING_SERVER" || -z "$ENV_BONDING_PORT" || -z "$ENV_BONDING_UUID" ]]; then
    ENV_ERRORS+=("BONDING_*: preencha BONDING_SERVER, BONDING_PORT e BONDING_UUID (ou deixe os três vazios)")
  else
    [[ "$ENV_BONDING_SERVER" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] \
      || ENV_ERRORS+=("BONDING_SERVER: deve ser um IPv4 (ex.: 203.0.113.10)")
    is_port "$ENV_BONDING_PORT" || ENV_ERRORS+=("BONDING_PORT: porta inválida")
    [[ "$ENV_BONDING_UUID" =~ ^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$ ]] \
      || ENV_ERRORS+=("BONDING_UUID: UUID inválido")
  fi
fi

for key in DEVICE_RETRY_ATTEMPTS DEVICE_RETRY_INTERVAL; do
  value="$(env_value "$key")"
  [[ -z "$value" || "$value" =~ ^[0-9]+$ ]] || ENV_ERRORS+=("$key: use um número inteiro")
done

if (( ${#ENV_ERRORS[@]} )); then
  echo "O .env precisa ser configurado antes de instalar:"
  printf '  - %s\n' "${ENV_ERRORS[@]}"
  echo "Edite com: nano .env   e rode de novo: ./install.sh"
  exit 1
fi
echo ".env ok (VPS: $VPS_HOST_V$([[ -n "$ENV_BONDING_SERVER" ]] && echo ", bonding: $ENV_BONDING_SERVER:$ENV_BONDING_PORT"))"

# --with-bsbf sem --server/--port/--uuid usa os BONDING_* do .env
BSBF_SERVER="${BSBF_SERVER:-$ENV_BONDING_SERVER}"
BSBF_PORT="${BSBF_PORT:-$ENV_BONDING_PORT}"
BSBF_UUID="${BSBF_UUID:-$ENV_BONDING_UUID}"

SUDO_PASSWORD="${PI_SUDO_PASSWORD:-$(env_value PI_SUDO_PASSWORD)}"
unset PI_SUDO_PASSWORD
if [[ -n "$SUDO_PASSWORD" ]]; then
  if ! printf '%s\n' "$SUDO_PASSWORD" | sudo -S -p '' -v 2>/dev/null; then
    echo "Senha do sudo incorreta — confira PI_SUDO_PASSWORD no .env."
    exit 1
  fi
  echo "==> sudo autenticado com PI_SUDO_PASSWORD"
  # Mantém o sudo autenticado até o fim (apt + BSBF podem passar dos 15 min do cache)
  ( while kill -0 "$$" 2>/dev/null; do sudo -n -v 2>/dev/null; sleep 50; done ) &
  SUDO_KEEPALIVE=$!
  trap 'kill "$SUDO_KEEPALIVE" 2>/dev/null || true' EXIT
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

  UVC_CONF=/etc/modprobe.d/uvcvideo.conf
  if [[ -f "$UVC_CONF" ]] && grep -qxF "$UVC_OPTIONS" "$UVC_CONF"; then
    echo "$UVC_CONF já configurado"
  else
    echo "$UVC_OPTIONS" | sudo tee "$UVC_CONF" >/dev/null
    echo "Gravado $UVC_CONF"
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
    fi
  else
    echo "cmdline.txt não encontrado — adicione usbcore.autosuspend=-1 manualmente."
  fi

  # uvcvideo.conf e cmdline.txt só valem após initramfs atualizado + reboot
  if command -v update-initramfs >/dev/null 2>&1; then
    sudo update-initramfs -u
  fi
fi

if [[ "$WITH_BSBF" -eq 1 ]]; then
  if [[ -z "$BSBF_SERVER" || -z "$BSBF_PORT" || -z "$BSBF_UUID" ]]; then
    echo "BSBF: preencha BONDING_SERVER, BONDING_PORT e BONDING_UUID no .env (ou --server/--port/--uuid)"
    exit 1
  fi
  echo "==> Instalando cliente BSBF"
  curl -fsSL cld.bondingshouldbefree.org | sudo sh -s -- \
    --server-ipv4 "$BSBF_SERVER" \
    --server-port "$BSBF_PORT" \
    --uuid "$BSBF_UUID"
  echo "BSBF instalado ($BSBF_SERVER:$BSBF_PORT). O app lê os mesmos dados do .env."
else
  echo "==> BSBF: o app instala o cliente sozinho ao iniciar a transmissão"
  echo "    se BONDING_* estiverem preenchidos no .env (ou no card Bonding)."
fi

# -k ignora a senha em cache do apt acima, para testar como o app vai rodar
if ! sudo -k -n true 2>/dev/null; then
  echo
  if [[ -n "$(env_value PI_SUDO_PASSWORD)" ]]; then
    echo "==> O app usará PI_SUDO_PASSWORD do .env para o sudo (instalar/ativar o BSBF)."
  else
    echo "AVISO: sudo pede senha para $USER. Para o app instalar/ativar o BSBF sozinho,"
    echo "defina PI_SUDO_PASSWORD no .env ou libere sudo sem senha (veja 'Sudo' no README)."
  fi
fi

echo
echo "Pronto. Inicie com: ./start-pi-irl.sh"
echo "ou: source .venv/bin/activate && python -m app.main"
echo
if [[ "$AUTO_REBOOT" -eq 1 ]]; then
  echo "Reiniciando em 10 s para aplicar tudo (uvcvideo, usbcore.autosuspend, initramfs, autostart)."
  echo "Ctrl+C cancela."
  sleep 10
  sudo reboot
else
  echo "Reinicie para aplicar tudo: sudo reboot"
fi
