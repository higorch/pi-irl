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

## Interface

**Dispositivos** — câmera, resolução, FPS, taxa de bits e microfone.

![Aba Dispositivos](assets/screenshot-01.png)

**Servidor (VPS)** — host do MediaMTX, porta SRT, ID da transmissão e URL RTSP para o OBS.

![Aba Servidor (VPS)](assets/screenshot-02.png)

**Conexões** — conexões de internet ativas e configuração do Bonding (BSBF).

![Aba Conexões](assets/screenshot-03.png)

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

## 3. Raspberry Pi — instalação

Tudo é feito pelo `install.sh`. Você só precisa preencher o `.env` e rodar o script.

### 1. Baixe e configure o `.env`

```bash
git clone https://github.com/higorch/pi-irl.git
cd pi-irl
cp .env.example .env
nano .env
```

```env
# Obrigatório
VPS_HOST=IP_OU_DOMINIO_DA_VPS
SRT_PORT=8890
STREAM_ID=irl

# Bonding (opcional): os três ou nenhum
BONDING_SERVER=IP_VPS
BONDING_PORT=PORTA_BSBF
BONDING_UUID=UUID_DO_CLIENTE

# Só se o sudo do Pi pedir senha
PI_SUDO_PASSWORD=
```

As demais variáveis têm padrão (tabela em [5. Arquivo `.env`](#5-arquivo-env)).

### 2. Rode o instalador

```bash
chmod +x install.sh
./install.sh
```

Rode como usuário normal, sem `sudo`. O script faz, em ordem:

1. **Confere o `.env`.** Se faltar algo, ou algum valor for inválido, lista o que corrigir e para sem instalar nada. Exemplos: `VPS_HOST` com o placeholder, porta inválida, `BONDING_*` incompleto, IPv4/UUID inválido, senha do sudo errada.
2. **Autentica o sudo** com `PI_SUDO_PASSWORD`, se preenchida, e o mantém ativo até o fim.
3. **Instala os pacotes:** FFmpeg, V4L2, ALSA, Python, git, curl.
4. **Cria o ambiente Python** (`.venv`) e instala as dependências.
5. **Cria o atalho** na área de trabalho e o **início automático** ao ligar o Pi.
6. **Ajusta a câmera USB:**
   - grava `options uvcvideo quirks=0x180 nodrop=1 timeout=5000` em `/etc/modprobe.d/uvcvideo.conf`;
   - acrescenta `usbcore.autosuspend=-1` em `cmdline.txt` (com backup);
   - roda `update-initramfs -u`.
7. **Instala o cliente BSBF**, só com `--with-bsbf`. Sem a opção, o app instala sozinho no primeiro **Iniciar transmissão**.
8. **Reinicia o Pi** em 10 s (Ctrl+C cancela), porque o ajuste da câmera só vale após o reboot.

O `.env` fica com permissão `600`, legível só pelo seu usuário, já que pode guardar a senha do sudo. Rodar o script de novo é seguro: o que já está configurado não é duplicado.

Opções:

| Opção | O que faz |
|-------|-----------|
| *(nenhuma)* | FFmpeg, V4L2, ALSA, Python/.venv, atalho, **início automático** ao ligar o Pi, **ajuste da câmera** e **reboot** no final |
| `--with-bsbf` | Instala o cliente BSBF já na instalação com os `BONDING_*` do `.env` (opcional, porque o app instala sozinho ao transmitir). `--server`/`--port`/`--uuid` sobrescrevem |
| `--no-autostart` | Remove/não cria o início automático |
| `--no-camera-fix` | Não aplica o ajuste da câmera |
| `--no-reboot` | Não reinicia sozinho (avisa para rodar `sudo reboot`) |

### 3. Pronto

Após o reboot, o Pi-IRL abre sozinho. Se a configuração já estiver completa, câmera e microfone salvos incluídos, ele começa a transmitir, conforme [Início automático](#início-automático-ao-ligar-o-pi). Na primeira vez, escolha câmera e microfone no app e clique em **Iniciar transmissão**; daí em diante tudo é automático.

---

## 4. Uso do app

Abas:

| Aba | Conteúdo |
|-----|----------|
| **Dispositivos** | Câmera e microfone conectados |
| **Servidor (VPS)** | Host MediaMTX, porta SRT, Stream ID, URL RTSP do OBS |
| **Conexões** | Card Internet (conexões ativas) + card Bonding (BSBF e avisos) |

1. Em **Servidor (VPS)**, confira Host / porta / ID (ou venha do `.env`).  
2. Em **Dispositivos**, escolha câmera e mic. Câmeras: só **USB**. Microfones: **USB** ou entrada **P2** (marcados `· USB` / `· P2`; virtuais e HDMI ficam de fora). No Raspberry o conector P2 da placa é só saída — para mic P2 use um adaptador de som USB com entrada P2 (aparece como USB) ou um HAT de áudio com entrada (aparece como P2). Conectou/removeu → a lista atualiza sozinha e o log registra.  
3. Em **Conexões**, veja as redes ativas; preencha o Bonding (BSBF) só se for usar.  
4. Clique **Iniciar transmissão**.  
5. No OBS: Media Source → `rtsp://IP_VPS:8554/irl`  
   - Formato de entrada: vazio  
   - Opções FFmpeg: `rtsp_transport=tcp`  
   - Buffer de rede: `0` MB  

### Bonding ao clicar em Iniciar transmissão

Com servidor (IPv4), porta e UUID preenchidos, **antes** de iniciar o FFmpeg o app:

| Situação no Pi | O que o app faz |
|----------------|-----------------|
| Cliente BSBF não instalado | Instala: `curl -fsSL cld.bondingshouldbefree.org \| sudo sh -s -- --server-ipv4 … --server-port … --uuid …` (alguns minutos) |
| Instalado com outro servidor/porta/UUID | Grava `/usr/local/etc/bsbf/bsbf-bonding.conf` e roda `bsbf-bonding --enable` |
| Instalado e parado | `bsbf-bonding --enable` |
| Instalado e ativo | Nada — transmite direto |

Depois disso o SRT sai normalmente: com o BSBF ativo, TCP e UDP para a internet passam pelo túnel agregado, sem mudar a URL.

Se algo falhar (sem internet, sudo com senha, erro na instalação), o motivo aparece no registro e a transmissão **segue sem agregação**. Sem bonding configurado, transmite normalmente.

Status do cliente no Pi: `sudo bsbf-bonding --status` · monitor web em `http://localhost:8080/`.

### Início automático ao ligar o Pi

O `install.sh` cria `~/.config/autostart/pi-irl.desktop` (abre o app com `--autostart` quando a área de trabalho carrega). Ao abrir, o app:

1. Espera `AUTOSTART_DELAY` segundos (padrão `30`) sem tocar na câmera, até o Pi, o USB, a área de trabalho e a rede terminarem de subir. Abrir a câmera logo após o boot a deixava instável: a transmissão caía 1–2 min depois.
2. Confere a configuração salva (Host, ID, câmera e microfone). Incompleta → só abre, sem transmitir.
3. Tenta conectar a câmera e o microfone USB salvos (e esperar a internet) a cada `DEVICE_RETRY_INTERVAL` segundos, até `DEVICE_RETRY_ATTEMPTS` tentativas (padrão: 10 tentativas de 10 em 10 s; `0` = sem limite). Se a câmera/mic acabou de aparecer no USB, espera mais um intervalo antes de abrir.
4. Inicia a transmissão (com bonding, se configurado). Se o FFmpeg falhar ao abrir câmera/mic nos primeiros 15 s, conta como tentativa e tenta de novo.
5. Ao vivo por 15 s sem erro → "transmissão estável" no registro e para de tentar. Clicar em **Parar** também interrompe as tentativas.

**Reconexão automática** (vale também para transmissões iniciadas no botão):
- Se a transmissão cai depois de ficar estável sem você clicar em **Parar**, o app tenta voltar com a mesma configuração. Usa as mesmas `DEVICE_RETRY_ATTEMPTS` e `DEVICE_RETRY_INTERVAL` e espera a câmera/mic reaparecerem no USB.
- **Câmera travada:** 10 s sem quadros novos (25 s para o primeiro), o FFmpeg é reiniciado e entra na reconexão.
- A câmera fica salva como `/dev/v4l/by-id/…` e o microfone como `hw:CARD=nome,DEV=n`. Se o USB reconectar e o Linux renumerar os dispositivos (`/dev/video0` → `/dev/video2`), o app continua achando os dois.
- Quando a transmissão cai, o registro avisa se o Pi teve **subtensão** (fonte fraca) ou limitou a CPU por **temperatura**. São as causas mais comuns de câmera e mic USB caírem juntos.

Requisitos: login automático na área de trabalho (padrão do Raspberry Pi OS) e ter transmitido ao menos uma vez pelo app (salva câmera/mic).  
Desativar: `./install.sh --no-autostart` ou `rm ~/.config/autostart/pi-irl.desktop`.

---

## 5. Arquivo `.env`

Criado a partir do `.env.example` antes do `./install.sh` (veja a seção 3).

| Variável | Descrição |
|----------|-----------|
| `VPS_HOST` | IP ou domínio da VPS (MediaMTX) |
| `SRT_PORT` | Porta SRT (padrão `8890`) |
| `STREAM_ID` | Path do stream (padrão `irl`) |
| `BONDING_SERVER` | IPv4 do servidor BSBF (opcional) |
| `BONDING_PORT` | Porta do cliente BSBF (opcional) |
| `BONDING_UUID` | UUID do cliente BSBF (opcional) |
| `AUTOSTART_DELAY` | Segundos de espera no boot antes de abrir a câmera (padrão `30`) |
| `DEVICE_RETRY_ATTEMPTS` | Tentativas de conectar câmera/mic USB no boot e ao reconectar após queda (padrão `10`, `0` = sem limite) |
| `DEVICE_RETRY_INTERVAL` | Segundos entre tentativas (padrão `10`, mínimo `2`) |
| `PI_SUDO_PASSWORD` | Senha do sudo do Pi para `install.sh` e bonding. Vazio = sudo sem senha, que é o padrão do Raspberry Pi OS. Use aspas se tiver espaços nas pontas. Não aparece em `ps` nem no registro |

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
| Bonding não sobe | Mensagem no registro · `sudo bsbf-bonding --status` · `systemctl status bsbf-mptcp xray-bsbf-bonding` · porta liberada na VPS |
| "sudo pediu senha" / "senha do sudo incorreta" | Defina/corrija `PI_SUDO_PASSWORD` no `.env` e rode `./install.sh` de novo |
| Câmera trava/cai | `vcgencmd get_throttled` deve dar `0x0`; diferente disso é fonte fraca ou temperatura, use a fonte oficial ou um hub USB com fonte · o ajuste da câmera do `install.sh` está ativo se `cat /sys/module/uvcvideo/parameters/quirks` der `384`; senão, `./install.sh` de novo |
| "ALSA xrun" / "Câmera indisponível" | USB ou CPU sobrecarregados: veja se há aviso de subtensão no registro, ligue câmera e mic em portas USB diferentes ou reduza resolução/FPS |
| Não transmite ao ligar | Registro do app mostra o que falta · `ls ~/.config/autostart/` · login automático ativo |
| MediaMTX offline | `systemctl status mediamtx` · `journalctl -u mediamtx -f` |
