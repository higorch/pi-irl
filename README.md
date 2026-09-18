# Pi-IRL

[![GitHub](https://img.shields.io/badge/GitHub-higorch%2Fpi--irl-181717?logo=github&logoColor=white)](https://github.com/higorch/pi-irl) [![License](https://img.shields.io/badge/License-Apache_2.0-D22128?logo=apache&logoColor=white)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%204-C51A4A?logo=raspberrypi&logoColor=white)](https://www.raspberrypi.com/)

Transmissão IRL no Raspberry Pi: câmera + microfone → **GStreamer** → **SRT** → **MediaMTX** (VPS) → **RTSP** / OBS.

**Testado em:** Raspberry Pi 4 Model B 4 GB · Raspberry Pi OS 64-bit.

```text
Câmera + Microfone
        ↓
   Pi-IRL / GStreamer
        ↓
   SRT  (+ BSBF opcional)
        ↓
   VPS / MediaMTX
        ↓
      RTSP → OBS
```

| Onde | O que roda |
|------|------------|
| **VPS** | MediaMTX · BSBF Server (opcional) |
| **Raspberry Pi** | Pi-IRL · GStreamer · BSBF Client (opcional) |

Sem bonding o fluxo já funciona. O BSBF só agrega Wi‑Fi + 4G (MPTCP) quando a internet do Pi é instável.

---

## Na VPS

### 1. MediaMTX v1.21.0

Servidor de mídia: recebe o SRT do Pi e entrega RTSP para o OBS.  
Doc oficial: [Introduction](https://mediamtx.org/docs/kickoff/introduction) · [Install](https://mediamtx.org/docs/kickoff/install)

Rodar na VPS como root (Linux amd64).

#### Remover instalação anterior

```bash
systemctl stop mediamtx 2>/dev/null || true
systemctl disable mediamtx 2>/dev/null || true
rm -f /etc/systemd/system/mediamtx.service
systemctl daemon-reload
rm -f /usr/local/bin/mediamtx
rm -rf /etc/mediamtx
rm -f /root/mediamtx_v1.21.0_linux_*.tar.gz
```

#### Instalar

```bash
cd /root
wget https://github.com/bluenviron/mediamtx/releases/download/v1.21.0/mediamtx_v1.21.0_linux_amd64.tar.gz
tar -xzf mediamtx_v1.21.0_linux_amd64.tar.gz
mv mediamtx /usr/local/bin/mediamtx
chmod +x /usr/local/bin/mediamtx

mediamtx --version
```

#### Configuração

```bash
mkdir -p /etc/mediamtx
cd /etc/mediamtx
wget https://raw.githubusercontent.com/bluenviron/mediamtx/v1.21.0/mediamtx.yml

# Desativa protocolos que o Pi-IRL não usa (mantém SRT + RTSP para o OBS)
sed -i 's/^rtmp: true/rtmp: false/' /etc/mediamtx/mediamtx.yml
sed -i 's/^hls: true/hls: false/' /etc/mediamtx/mediamtx.yml
sed -i 's/^webrtc: true/webrtc: false/' /etc/mediamtx/mediamtx.yml
sed -i 's/^moq: true/moq: false/' /etc/mediamtx/mediamtx.yml
```

> **Importante:** deixe `rtsp: true` e `srt: true`. Sem RTSP o OBS não consegue ler o stream.

#### Testar

```bash
/usr/local/bin/mediamtx /etc/mediamtx/mediamtx.yml
```

Confirme que sobe sem erro e saia com `Ctrl+C`.

#### Criar serviço

```bash
cat > /etc/systemd/system/mediamtx.service <<'EOF'
[Unit]
Description=MediaMTX
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/mediamtx /etc/mediamtx/mediamtx.yml
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

#### Ativar

```bash
systemctl daemon-reload
systemctl enable --now mediamtx
```

#### Ver status

```bash
systemctl status mediamtx --no-pager
systemctl is-active mediamtx
```

#### Ver logs

```bash
journalctl -u mediamtx -f
```

Liberar no firewall: `8890/udp` (SRT) e `8554/tcp` (RTSP).

| Stream ID | Pi publica | OBS lê |
|-----------|------------|--------|
| `irl` | `srt://IP_VPS:8890?mode=caller&streamid=publish:irl` | `rtsp://IP_VPS:8554/irl` |

### 2. Bonding BSBF (opcional — servidor)

```bash
curl -fsSL srv.bondingshouldbefree.org | sudo sh
```

Criar um cliente e anotar **porta** + **UUID**:

```bash
sudo bsbf-add-client 0
```

Exemplo de saída:

```text
Porta: 16384
UUID: 61e76964-ebdb-410b-a231-2dd6e2687a71
```

IP público e firewall:

```bash
curl -4 ifconfig.me
sudo ufw allow PORTA_BSBF/tcp
sudo ufw reload
```

Substitua `PORTA_BSBF` pela porta retornada (ex.: `16384`).

---

## No Raspberry Pi

### 1. GStreamer + ferramentas

Só o necessário para o pipeline IRL (V4L2 + ALSA → x264/AAC → SRT):

```bash
sudo apt-get update
sudo apt-get install -y \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav \
  gstreamer1.0-alsa \
  v4l-utils alsa-utils \
  python3 python3-venv python3-pip git
```

Conferir:

```bash
gst-inspect-1.0 srtsink x264enc avenc_aac v4l2src alsasrc
v4l2-ctl --list-devices
arecord -l
```

### 2. Pi-IRL

```bash
git clone https://github.com/higorch/pi-irl.git
cd pi-irl

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

chmod +x install-desktop-shortcut.sh start-pi-irl.sh
./install-desktop-shortcut.sh
```

Abra pelo ícone **Pi-IRL** ou `python -m app.main`.

No app: Host = IP/domínio da VPS · Porta SRT `8890` · Stream ID `irl` → **Iniciar transmissão**.

No OBS: Fonte → Media Source → `rtsp://IP_VPS:8554/irl`.

### 3. Bonding BSBF (opcional — cliente)

Use o IP, a porta e o UUID gerados na VPS:

```bash
curl -fsSL cld.bondingshouldbefree.org | sudo sh -s -- \
  --server-ipv4 IP_PUBLICO_DA_VPS \
  --server-port PORTA_BSBF \
  --uuid UUID_DO_CLIENTE
```

Verificar:

```bash
sudo systemctl status bsbf-mptcp --no-pager
```

Monitor: <http://localhost:8080/>

A publicação SRT do Pi-IRL não muda — o bonding só estabiliza o caminho até a VPS.

---

## Windows (só desenvolvimento da UI)

Instale o [GStreamer MSVC](https://gstreamer.freedesktop.org/download/) (plugins good/bad/ugly/libav) e coloque o `bin` no `PATH`.

```powershell
git clone https://github.com/higorch/pi-irl.git
cd pi-irl
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

---

## Problemas comuns

| Sintoma | O que fazer |
|---------|-------------|
| Plugin GStreamer ausente | Rodar de novo o `apt-get install` da seção do Pi |
| MediaMTX offline | `systemctl status mediamtx` · `journalctl -u mediamtx -f` · liberar `8890/udp` e `8554/tcp` |
| OBS sem vídeo | Conferir Stream ID, `rtsp://IP:8554/...` e status **Ao vivo** no Pi-IRL |
| Sem câmera / microfone | `v4l2-ctl` / `arecord -l` e **Procurar dispositivos** no app |
| App não abre no Pi | Precisa de sessão gráfica (desktop ou VNC) |

---

## Licença

Distribuído sob [Apache License 2.0](LICENSE).
