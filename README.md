# Pi-IRL

[![GitHub](https://img.shields.io/badge/GitHub-higorch%2Fpi--irl-181717?logo=github&logoColor=white)](https://github.com/higorch/pi-irl) [![License](https://img.shields.io/badge/License-Apache_2.0-D22128?logo=apache&logoColor=white)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%204-C51A4A?logo=raspberrypi&logoColor=white)](https://www.raspberrypi.com/)

Aplicação desktop para **transmissão IRL** a partir de um Raspberry Pi: captura câmera e microfone, envia o sinal pela internet e permite assistir/gravar no OBS.

**Testado em:** Raspberry Pi 4 Model B 4 GB com Raspberry Pi OS 64-bit.

---

## O que é e para que serve

O **Pi-IRL** é o painel no Raspberry Pi. Você escolhe câmera, microfone e o destino na VPS; o app monta e controla o **FFmpeg**, que publica o áudio/vídeo via **SRT**.

Sozinho o Pi não basta para o OBS na rede: quem recebe o SRT e entrega o stream em **RTSP** (e outros protocolos) é o **MediaMTX**, rodando em uma **VPS**. Assim o Pi só envia; a VPS concentra o stream e o OBS conecta nela.

Quando a internet do Pi é instável (Wi‑Fi + 4G), entra o **Bonding BSBF** (opcional): agrega links com MPTCP entre o Pi e a VPS, melhorando a estabilidade do caminho até o MediaMTX. O bonding cuida da rede; o Pi-IRL continua responsável pela captura e pela publicação SRT.

```text
Câmera + Microfone
        ↓
   Pi-IRL / FFmpeg
        ↓
   SRT  (+ bonding BSBF, opcional)
        ↓
   VPS / MediaMTX
        ↓
      RTSP
        ↓
       OBS
```

| Onde | Papel |
|------|--------|
| **Raspberry Pi** | App Pi-IRL, FFmpeg, câmera, microfone e, se usar bonding, o BSBF Client |
| **VPS** | MediaMTX (SRT → RTSP) e, se usar bonding, o BSBF Server |

> O Pi-IRL **não** configura o MediaMTX. Ele só publica via SRT. O OBS consome o RTSP gerado na VPS.

---

## MediaMTX na VPS

O **MediaMTX** é o servidor de mídia na nuvem. Ele:

1. Recebe a publicação SRT do Raspberry Pi  
2. Cria o path automaticamente com base no **Stream ID**  
3. Disponibiliza o stream em RTSP para o OBS (e outros clientes)

**Por que na VPS?** O Pi não precisa servir RTSP para a internet; a VPS tem IP estável e banda melhor; vários players podem ler o mesmo stream sem sobrecarregar o Pi.

| Protocolo | Porta padrão |
|-----------|-------------:|
| SRT | `8890` |
| RTSP | `8554` |
| RTMP | `1935` |
| HLS | `8888` |

No firewall da VPS, libere pelo menos **SRT (8890)** e **RTSP (8554)**.

| Stream ID | O Pi publica | O OBS lê |
|-----------|--------------|----------|
| `irl` | `srt://VPS:8890?mode=caller&streamid=publish:irl` | `rtsp://VPS:8554/irl` |
| `camera01` | `…streamid=publish:camera01` | `rtsp://VPS:8554/camera01` |

Substitua `VPS` pelo IP ou domínio do seu servidor.

---

## Bonding BSBF (opcional)

O **BSBF** (*Bonding Should Be Free*) agrega Wi‑Fi e modems 4G com **MPTCP**, para a transmissão IRL não cair quando uma das redes falha. É opcional: sem bonding o Pi-IRL + MediaMTX já funcionam; com bonding a rota até a VPS fica mais robusta.

### No servidor (VPS)

```bash
# Instalar o BSBF Server
curl -fsSL srv.bondingshouldbefree.org | sudo sh

# Criar um cliente e anotar PORTA_BSBF + UUID_DO_CLIENTE
sudo bsbf-add-client 0

# Descobrir o IP público e liberar a porta
curl -4 ifconfig.me
sudo ufw allow PORTA_BSBF/tcp
```

### No Raspberry Pi

```bash
curl -fsSL cld.bondingshouldbefree.org | sudo sh -s -- \
  --server-ipv4 IP_PUBLICO_DA_VPS \
  --server-port PORTA_BSBF \
  --uuid UUID_DO_CLIENTE

sudo systemctl status bsbf-mptcp --no-pager
```

| Verificação | Como |
|-------------|------|
| Monitor | <http://localhost:8080/> |
| Interfaces | `ip addr` |
| Endpoints MPTCP | `ip mptcp endpoint show` |

**Objetivo no app (bonding automático):** detectar Wi‑Fi e 4G, descobrir interfaces e IPs sem hardcodar nomes como `wwan0`/`usb0`, e adicionar/remover subflows MPTCP conforme os modems entram ou saem — deixando o BSBF fazer o bonding. A publicação SRT do Pi-IRL permanece a mesma.

---

## Instalar o Pi-IRL (Raspberry Pi)

### Requisitos

- Raspberry Pi 4 (testado no Model B 4 GB)  
- Raspberry Pi OS 64-bit e sessão gráfica  
- Câmera e microfone USB  
- FFmpeg no `PATH`  
- VPS com MediaMTX  
- Internet  

### Passo a passo

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg v4l-utils alsa-utils git

git clone https://github.com/higorch/pi-irl.git
cd pi-irl

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

chmod +x install-desktop-shortcut.sh start-pi-irl.sh
./install-desktop-shortcut.sh
```

Depois abra pelo ícone **Pi-IRL** na Área de Trabalho (ou `python -m app.main`).

### Conferir câmera, microfone e FFmpeg

```bash
v4l2-ctl --list-devices && ls /dev/video*
arecord -l
ffmpeg -version
```

### Configurar e transmitir

| Campo | Exemplo |
|-------|---------|
| Host URL/IP | `IP_OU_DOMINIO_DA_VPS` |
| Porta SRT | `8890` |
| Stream ID | `irl` |
| Câmera | `/dev/video0` |
| Microfone | `hw:3,0` |
| Resolução | `1280x720` |
| FPS / bitrate | `30` / `2500 kbps` (automáticos na UI) |

1. Clique em **Iniciar transmissão**  
2. Copie o **RTSP** mostrado no app  
3. No OBS: Fonte → Media Source → cole, por exemplo `rtsp://IP_OU_DOMINIO_DA_VPS:8554/irl`

---

## Windows (desenvolvimento)

Útil para testar a interface no PC. A captura usa DirectShow; o alvo de produção continua sendo o Raspberry Pi.

```powershell
git clone https://github.com/higorch/pi-irl.git
cd pi-irl
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Abra com duplo clique em `start-pi-irl.bat` ou `python -m app.main`.

---

## Problemas comuns

| Sintoma | O que fazer |
|---------|-------------|
| FFmpeg não encontrado | Instalar FFmpeg e garantir o `PATH` |
| App não abre no Pi | Usar desktop ou VNC (precisa de interface gráfica) |
| Atalho não executa | Rodar de novo `./install-desktop-shortcut.sh` e confiar no atalho |
| Sem câmera / microfone | `v4l2-ctl` / `arecord -l` e **Procurar dispositivos** no app |
| OBS sem vídeo | Conferir Stream ID, porta `8554` e status **Ao vivo** no Pi-IRL |

---

## Licença

Distribuído sob [Apache License 2.0](LICENSE).
