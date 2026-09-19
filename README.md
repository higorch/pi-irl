# Pi-IRL

[![GitHub](https://img.shields.io/badge/GitHub-higorch%2Fpi--irl-181717?logo=github&logoColor=white)](https://github.com/higorch/pi-irl) [![License](https://img.shields.io/badge/License-Apache_2.0-D22128?logo=apache&logoColor=white)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%204-C51A4A?logo=raspberrypi&logoColor=white)](https://www.raspberrypi.com/)

Transmissão IRL no Raspberry Pi: câmera + microfone → **FFmpeg** → **SRT** → **MediaMTX** (VPS) → **RTSP** / OBS.

**Testado em:** Raspberry Pi 4 Model B 4 GB · Raspberry Pi OS 64-bit.

```text
Câmera + Microfone
        ↓
   Pi-IRL / FFmpeg
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
| **Raspberry Pi** | Pi-IRL · FFmpeg · BSBF Client (opcional) |

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

sed -i \
  -e 's/^rtsp: .*/rtsp: true/' \
  -e 's/^srt: .*/srt: true/' \
  -e 's/^rtmp: .*/rtmp: false/' \
  -e 's/^hls: .*/hls: false/' \
  -e 's/^webrtc: .*/webrtc: false/' \
  -e 's/^moq: .*/moq: false/' \
  /etc/mediamtx/mediamtx.yml
```

Ativa **SRT** (entrada do Pi) e **RTSP** (saída para o OBS). Desliga RTMP, HLS, WebRTC e MoQ.

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

Se já estiver instalado e só mudar o YAML:

```bash
sed -i \
  -e 's/^rtsp: .*/rtsp: true/' \
  -e 's/^srt: .*/srt: true/' \
  -e 's/^rtmp: .*/rtmp: false/' \
  -e 's/^hls: .*/hls: false/' \
  -e 's/^webrtc: .*/webrtc: false/' \
  -e 's/^moq: .*/moq: false/' \
  /etc/mediamtx/mediamtx.yml && systemctl restart mediamtx
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

#### Portas e firewall

O MediaMTX deve escutar:

| Porta | Protocolo | Uso |
|------:|-----------|-----|
| `8890` | **UDP** | SRT (Pi → VPS) |
| `8554` | **TCP** | RTSP (OBS) |
| `8000` | **UDP** | RTP (RTSP) |
| `8001` | **UDP** | RTCP (RTSP) |

```bash
ss -ulnp | grep mediamtx
ss -tlnp | grep mediamtx
```

Exemplo esperado:

```text
udp UNCONN 0 0 *:8890 *:* users:(("mediamtx",...))
udp UNCONN 0 0 *:8000 *:* users:(("mediamtx",...))
udp UNCONN 0 0 *:8001 *:* users:(("mediamtx",...))
tcp LISTEN 0 4096 *:8554 *:* users:(("mediamtx",...))
```

Liberar no firewall:

```bash
ufw allow 8890/udp
ufw allow 8000/udp
ufw allow 8001/udp
ufw allow 8554/tcp
ufw reload
```

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

### 1. FFmpeg + ferramentas

```bash
sudo apt-get update
sudo apt-get install -y \
  ffmpeg \
  v4l-utils alsa-utils \
  python3 python3-venv python3-pip git
```

Conferir:

```bash
ffmpeg -version
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

No OBS: Fonte → Media Source → `rtsp://IP_VPS:8554/irl`

- **Formato de entrada:** vazio  
- **Opções do FFmpeg:** `rtsp_transport=tcp`  
- **Buffering de rede:** `0` MB (menor latência; se engasgar, suba para 1–2 MB)

### Câmera e microfone

O app lista só os dispositivos **conectados** (USB, CSI, jack). Escolha o nome na lista — sem digitar URL.

### Conferir webcam e testar o stream

Troque `IP_VPS`, `/dev/video0` e `hw:3,0`. MediaMTX precisa estar rodando.

No PC:

```bash
ffplay -rtsp_transport tcp rtsp://IP_VPS:8554/irl
```

#### 1. Formatos da câmera

```bash
v4l2-ctl --device /dev/video0 --list-formats-ext
```

Precisa ter **MJPG** (Motion-JPEG).

A captura adapta o formato da webcam ao que você escolhe. Resolução e FPS são selecionáveis (pré-marcados com a melhor opção da câmera). Bitrate vem com padrão sugerido e pode ser alterado.

Teste manual (troque devices/IP):

```bash
# Ver modos da câmera
v4l2-ctl --device /dev/video0 --list-formats-ext

# Publicar (o app monta algo equivalente ao melhor modo detectado)
ffmpeg -hide_banner -loglevel info \
  -fflags +genpts \
  -thread_queue_size 512 -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 -i /dev/video0 \
  -thread_queue_size 512 -f alsa -i hw:3,0 \
  -map 0:v:0 -map 1:a:0 \
  -vf fps=24,scale=1280:720,format=yuv420p \
  -c:v libx264 -preset veryfast -tune zerolatency -profile:v main \
  -g 48 -keyint_min 48 -sc_threshold 0 -bf 0 \
  -b:v 4000k -maxrate 4600k -bufsize 8000k \
  -c:a aac -ar 48000 -ac 1 -b:a 160k \
  -f mpegts "srt://IP_VPS:8890?mode=caller&streamid=publish:irl"
```

No PC: `ffplay -rtsp_transport tcp rtsp://IP_VPS:8554/irl` — deve listar `Video: h264` e `Audio: aac`.


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

Instale o [FFmpeg](https://ffmpeg.org/download.html) e coloque no `PATH`. A captura usa DirectShow; o alvo de produção é o Raspberry Pi.

```powershell
ffmpeg -version
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
| FFmpeg código 251 / falha ao iniciar | Webcam sem MJPEG 720p, device em uso ou Host SRT errado; veja o Registro do app |
| MediaMTX offline | `systemctl status mediamtx` · `journalctl -u mediamtx -f` · liberar `8890/udp`, `8000/udp`, `8001/udp`, `8554/tcp` |
| OBS / ffplay sem vídeo | Conferir MJPEG da webcam, Stream ID e status **Ao vivo** no Pi-IRL |
| Sem câmera / microfone | `v4l2-ctl` / `arecord -l` e **Procurar dispositivos** no app |
| App não abre no Pi | Precisa de sessão gráfica (desktop ou VNC) |

---

## Licença

Distribuído sob [Apache License 2.0](LICENSE).
