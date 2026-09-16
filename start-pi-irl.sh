#!/usr/bin/env bash
# Abre o Pi-IRL sem digitar o comando Python.
# Uso: chmod +x start-pi-irl.sh && ./start-pi-irl.sh
#      ou pelo atalho da Área de Trabalho (após install-desktop-shortcut.sh).

set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Ambiente .venv não encontrado."
  echo "Execute antes:"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  read -r -p "Pressione Enter para fechar..."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
exec python -m app.main
