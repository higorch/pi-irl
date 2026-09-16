# Pi-IRL

Aplicação desktop para Raspberry Pi que captura câmera e microfone e transmite via FFmpeg + SRT para uma VPS com MediaMTX.

Stack: **Python 3.11+** · **PySide6** · **FFmpeg**

Repositório: [https://github.com/higorch/pi-irl](https://github.com/higorch/pi-irl)

**Testado em:** Raspberry Pi 4 Model B 4 GB com o sistema operacional oficial de 64 bits (Raspberry Pi OS 64-bit).

```text
Câmera + Microfone
        ↓
      FFmpeg
        ↓
       SRT
        ↓
   VPS / MediaMTX
        ↓
       RTSP
        ↓
        OBS
```

---

## O que fica em cada lado

| Lado | Responsabilidade |
|------|------------------|
| **Raspberry Pi** | App Pi-IRL, FFmpeg, câmera, microfone, (opcional) BSBF Client / bonding |
| **VPS** | MediaMTX (recebe SRT e entrega RTSP), (opcional) BSBF Server |

O Pi-IRL **não** configura o MediaMTX. Ele só publica o stream via SRT. O OBS consome o RTSP gerado na VPS.

---

## MediaMTX na VPS

O MediaMTX roda **na VPS** e faz o papel de servidor de mídia:

1. Recebe a publicação SRT do Raspberry Pi.
2. Cria o path dinamicamente a partir do **Stream ID**.
3. Disponibiliza o stream em RTSP (e outros protocolos) para o OBS.

### Por que usar MediaMTX na VPS?

- O Raspberry Pi só precisa **enviar** (caller SRT); não precisa servir RTSP para a internet.
- A VPS tem IP público estável e banda melhor para o OBS conectar.
- Vários clientes (OBS, players) podem ler o mesmo stream sem sobrecarregar o Pi.
- O Stream ID define o path automaticamente (`irl`, `camera01`, etc.).

### Portas padrão do MediaMTX

| Serviço | Porta |
|---------|-------|
| SRT     | 8890  |
| RTSP    | 8554  |
| RTMP    | 1935  |
| HLS     | 8888  |

Libere no firewall da VPS pelo menos **8890/udp** (SRT) e **8554/tcp** (RTSP), conforme a sua configuração.

### Exemplo de publicação e leitura

No Pi-IRL:

```text
Host:       IP_OU_DOMINIO_DA_VPS
SRT Port:   8890
Stream ID:  irl
```

Publicação (montada pelo app):

```text
srt://IP_OU_DOMINIO_DA_VPS:8890?mode=caller&streamid=publish:irl
```

No OBS (RTSP):

```text
rtsp://IP_OU_DOMINIO_DA_VPS:8554/irl
```

Se o Stream ID for `camera01`:

```text
rtsp://IP_OU_DOMINIO_DA_VPS:8554/camera01
```

---

## Bonding BSBF — VPS + Raspberry Pi

Opcional. Use quando quiser agregar Wi‑Fi + 4G (MPTCP) entre o Pi e a VPS, melhorando a estabilidade da transmissão IRL.

### Lado VPS — BSBF Server

Instalar o BSBF Server:

```bash
curl -fsSL srv.bondingshouldbefree.org | sudo sh
```

Criar um cliente:

```bash
sudo bsbf-add-client 0
```

Exemplo de saída (use os valores gerados no seu servidor):

```text
Porta: PORTA_BSBF
UUID:  UUID_DO_CLIENTE
```

Descobrir o IP público da VPS:

```bash
curl -4 ifconfig.me
```

Liberar a porta no firewall (troque pela porta gerada):

```bash
sudo ufw allow PORTA_BSBF/tcp
```

### Lado Raspberry Pi — BSBF Client

Instalar o BSBF Client (substitua pelos valores da sua VPS):

```bash
curl -fsSL cld.bondingshouldbefree.org | sudo sh -s -- \
  --server-ipv4 IP_PUBLICO_DA_VPS \
  --server-port PORTA_BSBF \
  --uuid UUID_DO_CLIENTE
```

Verificar o serviço:

```bash
sudo systemctl status bsbf-mptcp --no-pager
```

Monitor local:

```text
http://localhost:8080/
```

Verificar interfaces:

```bash
ip addr
```

Verificar MPTCP:

```bash
ip mptcp endpoint show
```

### Bonding automático (objetivo do app)

O aplicativo desktop deverá:

1. Detectar Wi‑Fi e modems 4G.
2. Detectar automaticamente as interfaces de rede.
3. Detectar IP/conexão de cada modem.
4. Adicionar/remover os subflows MPTCP conforme os modems entram ou saem.
5. Deixar o BSBF realizar o bonding.

Não hardcodar nomes como `wwan0` ou `usb0`.

> A transmissão SRT do Pi-IRL continua independente: o bonding melhora o caminho de rede até a VPS; o MediaMTX continua recebendo o stream SRT na porta configurada.

---

## Pi-IRL (Raspberry Pi)

### Requisitos

- Raspberry Pi 4 Model B (testado com 4 GB)
- Raspberry Pi OS 64-bit
- Câmera USB
- Microfone USB
- FFmpeg
- VPS com MediaMTX configurado
- Conexão com a internet
- Sessão gráfica (desktop)

### Dependências do sistema

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg v4l-utils alsa-utils git
```

### Instalação

Clone o projeto:

```bash
git clone https://github.com/higorch/pi-irl.git
cd pi-irl
```

Crie o ambiente Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

### Abrir o app

**Atalho na Área de Trabalho (com ícone):**

```bash
chmod +x install-desktop-shortcut.sh start-pi-irl.sh
./install-desktop-shortcut.sh
```

Depois clique no ícone **Pi-IRL** na Área de Trabalho.

**Ou pelo terminal:**

```bash
source .venv/bin/activate
python -m app.main
```

### Configuração no Pi-IRL

Informe:

```text
Host URL/IP:  IP_OU_DOMINIO_DA_VPS
Porta SRT:    8890
Stream ID:    irl
```

Selecione:

```text
Câmera:     /dev/video0
Microfone:  hw:3,0
```

(Valores típicos no Pi; use **Procurar dispositivos** se forem outros.)

Vídeo (automático no app, só informativo):

```text
Resolução:  1280x720 (selecionável)
FPS:        30 (automático)
Bitrate:    2500 kbps (automático)
```

Clique em **Iniciar transmissão**.

Copie o **RTSP para o OBS** exibido na interface, por exemplo:

```text
rtsp://IP_OU_DOMINIO_DA_VPS:8554/irl
```

### Verificar dispositivos

Câmeras:

```bash
v4l2-ctl --list-devices
ls /dev/video*
```

Áudio:

```bash
arecord -l
```

### FFmpeg

```bash
ffmpeg -version
```

O FFmpeg deve estar no `PATH`. O checklist do app avisa se estiver faltando.

### Stream ID

O Stream ID cria o path dinamicamente no MediaMTX.

| Stream ID | Publicação SRT | RTSP |
|-----------|----------------|------|
| `irl` | `streamid=publish:irl` | `rtsp://VPS:8554/irl` |
| `camera01` | `streamid=publish:camera01` | `rtsp://VPS:8554/camera01` |

Use apenas letras, números, `_` e `-`.

### Teste

1. Confirme MediaMTX ativo na VPS.
2. Abra o Pi-IRL no Raspberry.
3. Configure o host da VPS, porta SRT e Stream ID.
4. Selecione câmera e microfone.
5. Clique em **Iniciar transmissão**.
6. No OBS: Fonte → Media Source → cole o RTSP gerado.

---

## Windows 11 (desenvolvimento)

```powershell
git clone https://github.com/higorch/pi-irl.git
cd pi-irl
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Abra com duplo clique em `start-pi-irl.bat` ou:

```powershell
python -m app.main
```

No Windows a captura usa DirectShow (para testar a UI). O alvo de produção é o Raspberry Pi.

---

## Estrutura

```text
pi-irl/
├── app/
├── assets/
│   └── pi-irl.png
├── install-desktop-shortcut.sh
├── start-pi-irl.sh
├── start-pi-irl.bat
├── requirements.txt
└── README.md
```

---

## Problemas comuns

| Problema | Solução |
|----------|---------|
| FFmpeg não encontrado | Instale o FFmpeg e confira o `PATH` |
| App não abre no Pi | Use sessão gráfica (desktop / VNC) |
| Atalho não executa | Rode `./install-desktop-shortcut.sh` e confie no atalho |
| Sem câmera / microfone | `v4l2-ctl` / `arecord -l` + **Procurar dispositivos** |
| OBS sem imagem | Confira Stream ID, porta 8554 e se o Pi está **Ao vivo** |
