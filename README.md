# Pi-IRL

[![GitHub](https://img.shields.io/badge/GitHub-higorch%2Fpi--irl-181717?logo=github&logoColor=white)](https://github.com/higorch/pi-irl) [![License](https://img.shields.io/badge/License-Apache_2.0-D22128?logo=apache&logoColor=white)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%204-C51A4A?logo=raspberrypi&logoColor=white)](https://www.raspberrypi.com/)

Transmissão IRL no Raspberry Pi: câmera + microfone → **FFmpeg** → **SRT** → **MediaMTX** (VPS) → **RTSP** / OBS.

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

---

## 1. VPS — MediaMTX

Recebe o SRT do Pi e entrega RTSP para o OBS.  
Docs: [Introduction](https://mediamtx.org/docs/kickoff/introduction) · [Install](https://mediamtx.org/docs/kickoff/install)

### Remover instalação anterior (se já existir)

```bash
systemctl stop mediamtx 2>/dev/null || true
systemctl disable mediamtx 2>/dev/null || true
rm -f /etc/systemd/system/mediamtx.service
systemctl daemon-reload
rm -f /usr/local/bin/mediamtx
rm -rf /etc/mediamtx
rm -f /root/mediamtx_v*_linux_*.tar.gz
```

### Instalar (Linux amd64, como root)

```bash
cd /root
wget https://github.com/bluenviron/mediamtx/releases/download/v1.21.0/mediamtx_v1.21.0_linux_amd64.tar.gz
tar -xzf mediamtx_v1.21.0_linux_amd64.tar.gz
mv mediamtx /usr/local/bin/mediamtx
chmod +x /usr/local/bin/mediamtx
mediamtx --version
```

### Configurar

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

### Serviço systemd

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

systemctl daemon-reload
systemctl enable --now mediamtx
systemctl status mediamtx --no-pager
```

### Firewall — só as portas usadas

Com o OBS em `rtsp_transport=tcp`, abra **apenas**:

| Porta | Protocolo | Uso |
|------:|-----------|-----|
| `8890` | UDP | SRT (Pi → VPS) |
| `8554` | TCP | RTSP (OBS) |

```bash
ufw allow 8890/udp comment 'MediaMTX SRT'
ufw allow 8554/tcp comment 'MediaMTX RTSP'
ufw reload
ufw status numbered
```

Não libere RTMP, HLS, WebRTC nem outras portas do MediaMTX.

### URLs

| Papel | URL |
|-------|-----|
| Pi publica | `srt://IP_VPS:8890?mode=caller&streamid=publish:irl` |
| OBS lê | `rtsp://IP_VPS:8554/irl` |

Logs: `journalctl -u mediamtx -f`

---

## 2. VPS — BSBF Server (opcional)

Bonding MPTCP ([BondingShouldBeFree](https://github.com/bondingshouldbefree)). Só precisa se for agregar Wi‑Fi + 4G no Pi.

### Remover instalação anterior (se já existir)

No **servidor** (VPS):

```bash
curl -fsSL https://github.com/bondingshouldbefree/bsbf-resources/raw/main/resources-server/bsbf-server-installer.sh \
  | sudo sh -s -- --uninstall
```

No **cliente** (Raspberry Pi), se o BSBF já estiver instalado:

```bash
sudo bsbf-bonding --uninstall
```

### Instalar servidor

```bash
curl -fsSL srv.bondingshouldbefree.org | sudo sh
```

### Criar cliente

```bash
sudo bsbf-add-client 0
```

Anote a **porta** e o **UUID** retornados. Exemplo:

```text
16384
61e76964-ebdb-410b-a231-2dd6e2687a71
```

### Firewall — só a porta do cliente BSBF

Abra **somente** a porta TCP retornada pelo `bsbf-add-client`. Nada além disso para o bonding.

```bash
# Exemplo: se a porta for 16384
sudo ufw allow 16384/tcp comment 'BSBF bonding'
sudo ufw reload
sudo ufw status numbered
```

Troque `16384` pela porta real do seu cliente. Não abra faixas inteiras “por precaução”.

### Resumo: portas abertas na VPS

| Serviço | Portas | Observação |
|---------|--------|------------|
| MediaMTX | `8890/udp`, `8554/tcp` | Sempre (SRT + RTSP/TCP) |
| BSBF | `PORTA_BSBF/tcp` | Só se usar bonding |

Nada mais de MediaMTX/BSBF precisa ficar aberto (sem `8000`/`8001`, RTMP, HLS, WebRTC, etc.).

---

## 3. Raspberry Pi — instalação completa

### Opção A — script único (recomendado)

```bash
git clone https://github.com/higorch/pi-irl.git
cd pi-irl
chmod +x install.sh start-pi-irl.sh
./install.sh
cp .env.example .env
nano .env
```

No `.env`, preencha pelo menos:

```env
VPS_HOST=IP_OU_DOMINIO_DA_VPS
SRT_PORT=8890
STREAM_ID=irl
```

Com bonding (use porta/UUID da VPS):

```bash
./install.sh --with-bsbf --server IP_VPS --port PORTA_BSBF --uuid UUID_DO_CLIENTE
```

E no `.env`:

```env
BONDING_SERVER=IP_VPS
BONDING_PORT=PORTA_BSBF
BONDING_UUID=UUID_DO_CLIENTE
```

Iniciar:

```bash
./start-pi-irl.sh
```

### Opção B — manual

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg v4l-utils alsa-utils python3 python3-venv python3-pip git curl

git clone https://github.com/higorch/pi-irl.git
cd pi-irl
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edite o .env
python -m app.main
```

Cliente BSBF (se não usou `--with-bsbf`):

```bash
curl -fsSL cld.bondingshouldbefree.org | sudo sh -s -- \
  --server-ipv4 IP_VPS \
  --server-port PORTA_BSBF \
  --uuid UUID_DO_CLIENTE
```

---

## 4. Uso do app

Abas:

| Aba | Conteúdo |
|-----|----------|
| **Dispositivos** | Câmera e microfone conectados |
| **Conexão** | Host MediaMTX, porta SRT, Stream ID, URL RTSP do OBS |
| **Internet (bonding)** | Links Wi‑Fi/4G/cabo + dados BSBF |

1. Em **Conexão**, confira Host / porta / ID (ou venha do `.env`).  
2. Em **Dispositivos**, escolha câmera e mic.  
3. Em **Internet (bonding)**, veja as redes; preencha BSBF só se for usar.  
4. Clique **Iniciar transmissão**.  
5. No OBS: Media Source → `rtsp://IP_VPS:8554/irl`  
   - Formato de entrada: vazio  
   - Opções FFmpeg: `rtsp_transport=tcp`  
   - Buffer de rede: `0` MB  

Bonding **não configurado** → transmite normalmente (aviso no registro).  
Bonding **configurado** → o app tenta subir o BSBF no mesmo clique.

---

## 5. Arquivo `.env`

```bash
cp .env.example .env
```

| Variável | Descrição |
|----------|-----------|
| `VPS_HOST` | IP ou domínio da VPS (MediaMTX) |
| `SRT_PORT` | Porta SRT (padrão `8890`) |
| `STREAM_ID` | Path do stream (padrão `irl`) |
| `BONDING_SERVER` | IP do BSBF (opcional) |
| `BONDING_PORT` | Porta do cliente BSBF (opcional) |
| `BONDING_UUID` | UUID do cliente BSBF (opcional) |

O `.env` completa/sobrescreve o `config.json` ao abrir o app. Não versione o `.env` (já está no `.gitignore`).

---

## 6. Windows (só UI / desenvolvimento)

```powershell
# FFmpeg no PATH: https://ffmpeg.org/download.html
git clone https://github.com/higorch/pi-irl.git
cd pi-irl
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

Bonding e a lista de redes são para Linux/Pi.

---

## Problemas comuns

| Sintoma | O que checar |
|---------|----------------|
| FFmpeg não encontrado | `ffmpeg -version` · rode `./install.sh` |
| Código 251 / falha ao iniciar | Câmera/mic, Host SRT, firewall `8890/udp` |
| OBS preto | Pi **Ao vivo**? `rtsp_transport=tcp`? Firewall `8554/tcp` |
| Bonding não sobe | Cliente instalado? Porta/UUID certos? `systemctl status bsbf-mptcp` |
| MediaMTX offline | `systemctl status mediamtx` · `journalctl -u mediamtx -f` |
