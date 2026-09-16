#!/usr/bin/env bash
# Cria atalho do Pi-IRL na Área de Trabalho e no menu de apps do Raspberry Pi.

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
ICON_SRC="$ROOT/assets/pi-irl.png"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_DIR="$HOME/Desktop"
# Alguns desktops usam "Área de Trabalho" em português
if [ ! -d "$DESKTOP_DIR" ] && [ -d "$HOME/Área de Trabalho" ]; then
  DESKTOP_DIR="$HOME/Área de Trabalho"
fi

mkdir -p "$ICON_DIR" "$APP_DIR"

chmod +x "$ROOT/start-pi-irl.sh"

if [ -f "$ICON_SRC" ]; then
  cp "$ICON_SRC" "$ICON_DIR/pi-irl.png"
  ICON_PATH="$ICON_DIR/pi-irl.png"
else
  ICON_PATH="camera-web"
fi

DESKTOP_FILE="$APP_DIR/pi-irl.desktop"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Pi-IRL
Comment=Transmissão IRL no Raspberry Pi
Exec=$ROOT/start-pi-irl.sh
Path=$ROOT
Icon=$ICON_PATH
Terminal=false
Categories=AudioVideo;Video;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

if [ -d "$DESKTOP_DIR" ]; then
  cp "$DESKTOP_FILE" "$DESKTOP_DIR/Pi-IRL.desktop"
  chmod +x "$DESKTOP_DIR/Pi-IRL.desktop"
  # Raspberry Pi OS / LXDE às vezes exige "confiar" no atalho
  if command -v gio >/dev/null 2>&1; then
    gio set "$DESKTOP_DIR/Pi-IRL.desktop" metadata::trusted true 2>/dev/null || true
  fi
  echo "Atalho criado em: $DESKTOP_DIR/Pi-IRL.desktop"
else
  echo "Pasta Desktop não encontrada. Atalho disponível no menu de aplicativos."
fi

echo "Atalho no menu: $DESKTOP_FILE"
echo "Pronto. Use o ícone Pi-IRL na área de trabalho para abrir o app."
