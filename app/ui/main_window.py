"""Janela principal do Pi-IRL."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPaintEvent,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import load_config, save_config
from app.models.stream_config import StreamConfig, StreamStatus
from app.services import devices
from app.services.ffmpeg import FFmpegService
from app.services.media_profile import (
    list_fps_choices,
    list_resolution_choices,
    probe_best_profile,
    recommend_defaults,
    suggested_bitrate,
)
from app.services.stream import StreamService
from app.ui.styles import APP_STYLESHEET, COMPACT_STYLESHEET

# Portas padrão do MediaMTX (referência na UI / URL RTSP)
MEDIAMTX_SRT_PORT = 8890
MEDIAMTX_RTSP_PORT = 8554
MEDIAMTX_RTMP_PORT = 1935
MEDIAMTX_HLS_PORT = 8888

# Valores padrão (pré-seleção / fallback)
AUTO_FPS = 24
AUTO_BITRATE_KBPS = 4000
AUTO_GOP = 48
AUTO_AUDIO_CHANNELS = 1

ARROW_COLOR = "#9aa3b5"
# Telas ~3.5" (ex.: 480x320) e afins
SMALL_SCREEN_WIDTH = 700
SMALL_SCREEN_HEIGHT = 500


class SelectBox(QComboBox):
    """Combo com seta própria: o stylesheet remove a seta nativa do Qt."""

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(ARROW_COLOR))

        center_x = self.width() - 14
        center_y = self.height() / 2
        size = 4 if self.height() < 34 else 5
        arrow = QPolygonF(
            [
                QPointF(center_x - size, center_y - 2),
                QPointF(center_x + size, center_y - 2),
                QPointF(center_x, center_y + size - 1),
            ]
        )
        painter.drawPolygon(arrow)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pi-IRL")

        self._compact = self._detect_compact_screen()
        self._input_height = 34 if self._compact else 40
        self._field_gap = 10 if self._compact else 14
        self._label_gap = 5 if self._compact else 7

        if self._compact:
            self.resize(480, 320)
            self.setMinimumSize(320, 240)
            self.setStyleSheet(APP_STYLESHEET + COMPACT_STYLESHEET)
        else:
            self.resize(980, 760)
            self.setMinimumSize(480, 360)
            self.setStyleSheet(APP_STYLESHEET)

        self._config = load_config()
        self._stream = StreamService(self)
        self._ffmpeg_ready = False
        self._current_rtsp_url = ""

        self._build_ui()
        self._populate_devices()
        self._apply_config_to_ui(self._config)
        self._connect_signals()
        self._update_buttons(StreamStatus.OFFLINE)
        self._set_status_badge(StreamStatus.OFFLINE)
        self._refresh_dependencies()
        self._update_rtsp_url()

    def _detect_compact_screen(self) -> bool:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return False
        size = screen.availableGeometry()
        return size.width() <= SMALL_SCREEN_WIDTH or size.height() <= SMALL_SCREEN_HEIGHT

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("rootArea")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        margin = 10 if self._compact else 24
        root.setContentsMargins(margin, margin, margin, margin)
        root.setSpacing(10 if self._compact else 14)

        root.addWidget(self._build_header())
        root.addWidget(self._build_content_scroll(), stretch=1)
        root.addWidget(self._build_controls())

    def _build_content_scroll(self) -> QScrollArea:
        content = QWidget()
        content.setObjectName("scrollContent")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(self._field_gap)
        layout.addWidget(self._build_deps_card())
        layout.addWidget(self._build_connection_card())
        layout.addWidget(self._build_video_card())
        layout.addWidget(self._build_audio_card())
        layout.addWidget(self._build_log_card(), stretch=1)

        scroll = QScrollArea()
        scroll.setObjectName("configScroll")
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return scroll

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10 if self._compact else 20)

        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(2)

        brand = QLabel("Pi-IRL")
        brand.setObjectName("brandLabel")

        subtitle = QLabel("Transmissão IRL no Raspberry Pi")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)

        titles.addWidget(brand)
        titles.addWidget(subtitle)

        self.status_badge = QLabel("● Offline")
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setFixedHeight(30 if self._compact else 36)
        self.status_badge.setMinimumWidth(100 if self._compact else 130)

        layout.addLayout(titles, stretch=1)
        layout.addWidget(self.status_badge, alignment=Qt.AlignmentFlag.AlignTop)

        header.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return header

    def _build_deps_card(self) -> QFrame:
        """Checklist sutil de dependências + portas MediaMTX."""
        card = QFrame()
        card.setObjectName("depsCard")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(card)
        pad_h = 10 if self._compact else 14
        pad_v = 8 if self._compact else 10
        layout.setContentsMargins(pad_h, pad_v, pad_h, pad_v)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        title = QLabel("Status")
        title.setObjectName("depsTitle")

        self.recheck_deps_button = QPushButton("↻")
        self.recheck_deps_button.setObjectName("depsRecheckButton")
        self.recheck_deps_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recheck_deps_button.setToolTip("Verificar novamente")
        self.recheck_deps_button.setFixedSize(28, 28)

        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.recheck_deps_button)
        layout.addLayout(top)

        chips = QHBoxLayout() if not self._compact else QVBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)

        self.dep_ffmpeg_label = QLabel()
        self.dep_camera_label = QLabel()
        self.dep_mic_label = QLabel()
        for item in (
            self.dep_ffmpeg_label,
            self.dep_camera_label,
            self.dep_mic_label,
        ):
            item.setObjectName("depsChip")
            item.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            chips.addWidget(item)

        if not self._compact:
            chips.addStretch(1)

        layout.addLayout(chips)

        ports = QLabel(
            f"MediaMTX · SRT {MEDIAMTX_SRT_PORT} · "
            f"RTSP {MEDIAMTX_RTSP_PORT} · "
            f"RTMP {MEDIAMTX_RTMP_PORT} · "
            f"HLS {MEDIAMTX_HLS_PORT}"
        )
        ports.setObjectName("depsPorts")
        ports.setWordWrap(True)
        layout.addWidget(ports)

        self._deps_card = card
        return card

    def _make_card(
        self,
        title: str,
        *,
        expanding: bool = False,
    ) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")

        outer = QVBoxLayout(card)
        pad = 12 if self._compact else 18
        outer.setContentsMargins(pad, pad - 2, pad, pad)
        outer.setSpacing(10 if self._compact else 12)

        if expanding:
            card.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Expanding,
            )
        else:
            card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            outer.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)

        section = QLabel(title)
        section.setObjectName("sectionTitle")
        section.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        outer.addWidget(section)
        return card, outer

    def _field(self, label: str, widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._label_gap)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        text = QLabel(label)
        text.setObjectName("fieldLabel")
        text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        text.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        text.setMinimumHeight(text.fontMetrics().height())

        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setMinimumHeight(self._input_height)

        layout.addWidget(text)
        layout.addWidget(widget)

        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return container

    def _info_value(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("infoValue")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setMinimumHeight(self._input_height)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return label

    def _stack(self, *widgets: QWidget) -> QWidget:
        """Empilha campos verticalmente — adequado a telas estreitas."""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._field_gap)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        for widget in widgets:
            layout.addWidget(widget)
        box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return box

    def _row(self, *fields: QWidget, stretches: list[int] | None = None) -> QWidget:
        """Linha horizontal; em modo compacto vira pilha vertical."""
        if self._compact:
            return self._stack(*fields)

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._field_gap)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        if stretches is None:
            stretches = [1] * len(fields)

        for field, stretch in zip(fields, stretches, strict=True):
            layout.addWidget(field, stretch)

        row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return row

    def _device_picker(
        self,
        combo: QComboBox,
        button: QPushButton,
    ) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap) if not self._compact else QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        combo.setMinimumHeight(self._input_height)
        button.setMinimumHeight(self._input_height)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setObjectName("refreshButton")

        if self._compact:
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(combo)
            layout.addWidget(button)
        else:
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            layout.addWidget(combo, stretch=1)
            layout.addWidget(button)

        wrap.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return wrap

    def _build_connection_card(self) -> QFrame:
        card, layout = self._make_card("Conexão")

        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("IP ou URL do servidor")
        self.host_edit.setClearButtonEnabled(True)

        self.srt_port_spin = QSpinBox()
        self.srt_port_spin.setRange(1, 65535)
        self.srt_port_spin.setValue(8890)

        self.stream_id_edit = QLineEdit()
        self.stream_id_edit.setPlaceholderText("Ex.: irl")
        self.stream_id_edit.setClearButtonEnabled(True)

        layout.addWidget(self._field("Host URL/IP", self.host_edit))
        layout.addWidget(
            self._row(
                self._field("Porta SRT", self.srt_port_spin),
                self._field("ID da transmissão", self.stream_id_edit),
                stretches=[1, 2],
            )
        )

        self.rtsp_value = QLabel("rtsp://—:8554/—")
        self.rtsp_value.setObjectName("rtspValue")
        self.rtsp_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.rtsp_value.setWordWrap(True)
        self.rtsp_value.setMinimumHeight(self._input_height)

        self.copy_rtsp_button = QPushButton("Copiar")
        self.copy_rtsp_button.setObjectName("copyButton")
        self.copy_rtsp_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_rtsp_button.setToolTip("Copiar URL RTSP para usar no OBS")
        self.copy_rtsp_button.setMinimumHeight(self._input_height)

        rtsp_row = QWidget()
        rtsp_layout = QHBoxLayout(rtsp_row) if not self._compact else QVBoxLayout(rtsp_row)
        rtsp_layout.setContentsMargins(0, 0, 0, 0)
        rtsp_layout.setSpacing(8)
        rtsp_layout.addWidget(self.rtsp_value, stretch=1)
        rtsp_layout.addWidget(self.copy_rtsp_button)

        rtsp_hint = QLabel(
            f"OBS · Media Source · porta RTSP padrão {MEDIAMTX_RTSP_PORT}"
        )
        rtsp_hint.setObjectName("rtspHint")
        rtsp_hint.setWordWrap(True)

        layout.addWidget(self._field("RTSP para o OBS", rtsp_row))
        layout.addWidget(rtsp_hint)
        return card

    def _build_video_card(self) -> QFrame:
        card, layout = self._make_card("Vídeo")

        self.camera_combo = SelectBox()
        self.camera_combo.setEditable(False)

        self.refresh_video_button = QPushButton("Procurar dispositivos")
        self.refresh_video_button.setToolTip("Atualizar lista de câmeras")

        camera_input = self._device_picker(self.camera_combo, self.refresh_video_button)

        self.resolution_combo = SelectBox()
        self.resolution_combo.setEditable(False)

        self.fps_combo = SelectBox()
        self.fps_combo.setEditable(False)

        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(500, 12000)
        self.bitrate_spin.setSingleStep(100)
        self.bitrate_spin.setSuffix(" kbps")
        self.bitrate_spin.setValue(AUTO_BITRATE_KBPS)
        self.bitrate_spin.setFixedHeight(self._input_height)

        layout.addWidget(self._field("Câmera", camera_input))
        layout.addWidget(
            self._row(
                self._field("Resolução", self.resolution_combo),
                self._field("FPS", self.fps_combo),
                stretches=[2, 1],
            )
        )
        layout.addWidget(self._field("Taxa de bits", self.bitrate_spin))
        return card

    def _build_audio_card(self) -> QFrame:
        card, layout = self._make_card("Áudio")

        self.microphone_combo = SelectBox()
        self.microphone_combo.setEditable(False)

        self.refresh_audio_button = QPushButton("Procurar dispositivos")
        self.refresh_audio_button.setToolTip("Atualizar lista de microfones")

        mic_input = self._device_picker(
            self.microphone_combo,
            self.refresh_audio_button,
        )

        layout.addWidget(self._field("Microfone", mic_input))
        return card

    def _build_controls(self) -> QWidget:
        controls = QWidget()
        layout = QVBoxLayout(controls) if self._compact else QHBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8 if self._compact else 14)

        btn_height = 42 if self._compact else 48

        self.start_button = QPushButton("Iniciar transmissão")
        self.start_button.setObjectName("startButton")
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.setFixedHeight(btn_height)

        self.stop_button = QPushButton("Parar transmissão")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setFixedHeight(btn_height)

        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)

        controls.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return controls

    def _build_log_card(self) -> QFrame:
        card, layout = self._make_card("Registro", expanding=True)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setPlaceholderText("A saída do FFmpeg aparece aqui...")
        self.log_view.setMinimumHeight(56 if self._compact else 80)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        if self._compact:
            font.setPointSize(9)
        self.log_view.setFont(font)
        layout.addWidget(self.log_view)
        return card

    def _populate_devices(self) -> None:
        current_camera = self._combo_value(self.camera_combo)
        current_mic = self._combo_value(self.microphone_combo)

        self.camera_combo.clear()
        cameras = devices.list_cameras()
        if cameras:
            for camera in cameras:
                self.camera_combo.addItem(camera.label, camera.value)
        else:
            self.camera_combo.addItem("Nenhuma câmera encontrada", "")

        self.microphone_combo.clear()
        microphones = devices.list_microphones()
        if microphones:
            for mic in microphones:
                self.microphone_combo.addItem(mic.label, mic.value)
        else:
            self.microphone_combo.addItem("Nenhum microfone encontrado", "")

        # Só restaura seleção anterior se o dispositivo ainda existir de verdade
        if current_camera and any(c.value == current_camera for c in cameras):
            self._select_combo_value(self.camera_combo, current_camera)
        if current_mic and any(m.value == current_mic for m in microphones):
            self._select_combo_value(self.microphone_combo, current_mic)

        self._refresh_video_options(prefer_recommend=True)

    def _refresh_video_options(self, *, prefer_recommend: bool = False) -> None:
        """Preenche resolução/FPS e pré-seleciona o melhor (ou mantém a escolha atual)."""
        camera = str(self._combo_value(self.camera_combo) or "").strip()
        microphone = str(self._combo_value(self.microphone_combo) or "").strip()

        current_res = str(self._combo_value(self.resolution_combo) or "").strip()
        current_fps = self._combo_value(self.fps_combo)

        resolutions = list_resolution_choices(camera)
        fps_values = list_fps_choices(camera)

        self.resolution_combo.blockSignals(True)
        self.fps_combo.blockSignals(True)
        self.resolution_combo.clear()
        self.fps_combo.clear()

        for value in resolutions:
            self.resolution_combo.addItem(value, value)
        for fps in fps_values:
            self.fps_combo.addItem(f"{fps} fps", fps)

        rec_res, rec_fps, rec_bitrate = (
            recommend_defaults(camera, microphone)
            if camera
            else ("1280x720", AUTO_FPS, AUTO_BITRATE_KBPS)
        )

        if prefer_recommend or not current_res or current_res not in resolutions:
            self._select_combo_value(self.resolution_combo, rec_res)
        else:
            self._select_combo_value(self.resolution_combo, current_res)

        if prefer_recommend or current_fps is None or current_fps not in fps_values:
            self._select_combo_value(self.fps_combo, rec_fps)
        else:
            self._select_combo_value(self.fps_combo, current_fps)

        self.resolution_combo.blockSignals(False)
        self.fps_combo.blockSignals(False)

        # Bitrate sugerido ao trocar câmera / ao recomendar
        if prefer_recommend:
            self.bitrate_spin.setValue(rec_bitrate)
        else:
            self._sync_suggested_bitrate()

    def _sync_suggested_bitrate(self) -> None:
        """Atualiza o bitrate sugerido conforme resolução/FPS (usuário ainda pode editar)."""
        resolution = str(self._combo_value(self.resolution_combo) or "1280x720")
        fps = int(self._combo_value(self.fps_combo) or AUTO_FPS)
        try:
            w, h = (int(x) for x in resolution.lower().split("x", 1))
            self.bitrate_spin.setValue(suggested_bitrate(w, h, fps))
        except ValueError:
            self.bitrate_spin.setValue(AUTO_BITRATE_KBPS)

    def _apply_config_to_ui(self, config: StreamConfig) -> None:
        self.host_edit.setText(config.vps_host)
        self.srt_port_spin.setValue(config.srt_port)
        self.stream_id_edit.setText(config.stream_id)
        self._select_combo_value(self.camera_combo, config.camera, allow_missing=False)
        self._select_combo_value(
            self.microphone_combo,
            config.microphone,
            allow_missing=False,
        )
        self._refresh_video_options(prefer_recommend=not bool(config.resolution))
        if config.resolution:
            self._select_combo_value(self.resolution_combo, config.resolution)
        if config.fps:
            self._select_combo_value(self.fps_combo, config.fps)
        if config.bitrate_kbps:
            self.bitrate_spin.setValue(config.bitrate_kbps)

    def _select_combo_value(
        self,
        combo: QComboBox,
        value: object,
        *,
        allow_missing: bool = True,
    ) -> None:
        if value is None or value == "":
            return

        index = combo.findData(value)
        if index < 0:
            index = combo.findText(str(value))
        if index >= 0:
            combo.setCurrentIndex(index)
            return

        # Não reinsere dispositivos desconectados salvos no config
        if not allow_missing:
            return

        combo.addItem(str(value), value)
        combo.setCurrentIndex(combo.count() - 1)

    def _combo_value(self, combo: QComboBox) -> object:
        if combo.count() == 0:
            return ""
        data = combo.currentData()
        if data is None:
            return combo.currentText().strip()
        return data

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.refresh_video_button.clicked.connect(self._on_refresh_video)
        self.refresh_audio_button.clicked.connect(self._on_refresh_audio)
        self.recheck_deps_button.clicked.connect(self._refresh_dependencies)
        self.copy_rtsp_button.clicked.connect(self._on_copy_rtsp)
        self.host_edit.textChanged.connect(self._update_rtsp_url)
        self.stream_id_edit.textChanged.connect(self._update_rtsp_url)
        self.camera_combo.currentIndexChanged.connect(
            lambda: self._refresh_video_options(prefer_recommend=True)
        )
        self.microphone_combo.currentIndexChanged.connect(
            lambda: self._refresh_video_options(prefer_recommend=False)
        )
        self.resolution_combo.currentIndexChanged.connect(self._sync_suggested_bitrate)
        self.fps_combo.currentIndexChanged.connect(self._sync_suggested_bitrate)
        self._stream.status_changed.connect(self._on_status_changed)
        self._stream.log_line.connect(self._append_log)
        self._stream.validation_failed.connect(self._on_validation_failed)

    def _collect_config(self) -> StreamConfig:
        camera = str(self._combo_value(self.camera_combo) or "").strip()
        microphone = str(self._combo_value(self.microphone_combo) or "").strip()
        resolution = str(self._combo_value(self.resolution_combo) or "1280x720").strip()
        fps = int(self._combo_value(self.fps_combo) or AUTO_FPS)
        bitrate = int(self.bitrate_spin.value())
        profile = (
            probe_best_profile(
                camera,
                microphone,
                output_resolution=resolution,
                output_fps=fps,
                bitrate_kbps=bitrate,
            )
            if camera
            else None
        )

        return StreamConfig(
            vps_host=self.host_edit.text().strip(),
            srt_port=self.srt_port_spin.value(),
            stream_id=self.stream_id_edit.text().strip(),
            camera=camera,
            resolution=resolution,
            fps=fps,
            bitrate_kbps=bitrate,
            microphone=microphone,
            audio_channels=profile.audio_channels if profile else AUTO_AUDIO_CHANNELS,
            sample_rate=profile.sample_rate if profile else 48000,
            gop=profile.gop if profile else max(fps * 2, 1),
        )

    def _on_start_clicked(self) -> None:
        config = self._collect_config()
        save_config(config)
        self._stream.start(config)

    def _on_stop_clicked(self) -> None:
        self._stream.stop()

    def _on_refresh_video(self) -> None:
        current_mic = self._combo_value(self.microphone_combo)
        self._populate_devices()
        self._select_combo_value(self.microphone_combo, current_mic)
        self._refresh_dependencies()
        self._append_log("Câmeras atualizadas.")

    def _on_refresh_audio(self) -> None:
        current_cam = self._combo_value(self.camera_combo)
        self._populate_devices()
        self._select_combo_value(self.camera_combo, current_cam)
        self._refresh_dependencies()
        self._append_log("Microfones atualizados.")

    def _refresh_dependencies(self) -> None:
        """Atualiza o checklist sutil de dependências (sem modal)."""
        ffmpeg_path = FFmpegService.resolve_ffmpeg_path()
        ffmpeg_ok = ffmpeg_path is not None

        camera = str(self._combo_value(self.camera_combo) or "").strip()
        microphone = str(self._combo_value(self.microphone_combo) or "").strip()
        camera_ok = bool(camera) and camera != "Nenhuma câmera encontrada"
        mic_ok = bool(microphone) and microphone != "Nenhum microfone encontrado"

        self._set_dep_chip(
            self.dep_ffmpeg_label,
            ok=ffmpeg_ok,
            label="FFmpeg",
            detail=ffmpeg_path or "ffmpeg não encontrado no PATH",
        )
        self._set_dep_chip(
            self.dep_camera_label,
            ok=camera_ok,
            label="Câmera",
            detail=camera if camera_ok else "Nenhuma detectada",
        )
        self._set_dep_chip(
            self.dep_mic_label,
            ok=mic_ok,
            label="Microfone",
            detail=microphone if mic_ok else "Nenhum detectado",
        )

        self._ffmpeg_ready = ffmpeg_ok
        if not self._stream.is_active:
            self.start_button.setEnabled(ffmpeg_ok)

    def _set_dep_chip(
        self,
        chip: QLabel,
        *,
        ok: bool,
        label: str,
        detail: str,
    ) -> None:
        icon = "✔" if ok else "✖"
        chip.setObjectName("depsChipOk" if ok else "depsChipError")
        chip.setText(f"  {icon}  {label}  ")
        chip.setToolTip(detail)
        chip.style().unpolish(chip)
        chip.style().polish(chip)

    def _update_rtsp_url(self) -> None:
        host = self.host_edit.text().strip() or "IP_DA_VPS"
        stream_id = self.stream_id_edit.text().strip() or "STREAM_ID"
        url = f"rtsp://{host}:{MEDIAMTX_RTSP_PORT}/{stream_id}"
        self.rtsp_value.setText(url)
        self._current_rtsp_url = url

    def _on_copy_rtsp(self) -> None:
        url = getattr(self, "_current_rtsp_url", self.rtsp_value.text())
        QApplication.clipboard().setText(url)
        self._append_log(f"RTSP copiado: {url}")
        self.copy_rtsp_button.setText("Copiado!")
        self.copy_rtsp_button.setEnabled(False)

        def restore() -> None:
            self.copy_rtsp_button.setText("Copiar")
            self.copy_rtsp_button.setEnabled(True)

        QTimer.singleShot(1500, restore)

    def _on_status_changed(self, status: str) -> None:
        try:
            enum_status = StreamStatus(status)
        except ValueError:
            enum_status = StreamStatus.OFFLINE
        self._set_status_badge(enum_status)
        self._update_buttons(enum_status)

    def _set_status_badge(self, status: StreamStatus) -> None:
        colors = {
            StreamStatus.OFFLINE: ("#8f98a8", "#22272f", "#333a46"),
            StreamStatus.STARTING: ("#f0c040", "#3a3018", "#7a6218"),
            StreamStatus.STOPPING: ("#f0c040", "#3a3018", "#7a6218"),
            StreamStatus.LIVE: ("#3dd68c", "#143526", "#1f7a4d"),
            StreamStatus.ERROR: ("#ff6b6b", "#3a1818", "#8a2f2f"),
        }
        text_color, bg, border = colors[status]
        self.status_badge.setText(f"● {status.label_pt}")
        pad = "0 10px" if self._compact else "0 16px"
        self.status_badge.setStyleSheet(
            f"""
            QLabel#statusBadge {{
                color: {text_color};
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 15px;
                padding: {pad};
                font-size: {"11px" if self._compact else "12px"};
                font-weight: 800;
            }}
            """
        )

    def _update_buttons(self, status: StreamStatus) -> None:
        active = status in (
            StreamStatus.STARTING,
            StreamStatus.LIVE,
            StreamStatus.STOPPING,
        )
        self.start_button.setEnabled(
            not active and getattr(self, "_ffmpeg_ready", True)
        )
        self.stop_button.setEnabled(active and status != StreamStatus.STOPPING)
        self.refresh_video_button.setEnabled(not active)
        self.refresh_audio_button.setEnabled(not active)
        self.recheck_deps_button.setEnabled(not active)
        self.camera_combo.setEnabled(not active)
        self.microphone_combo.setEnabled(not active)
        self.resolution_combo.setEnabled(not active)
        self.fps_combo.setEnabled(not active)
        self.bitrate_spin.setEnabled(not active)

    def _append_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{stamp}] {message}")

    def _on_validation_failed(self, message: str) -> None:
        self._append_log(message.replace("\n", " | "))
        QMessageBox.warning(self, "Atenção", message)

    def closeEvent(self, event: QCloseEvent) -> None:
        save_config(self._collect_config())
        if self._stream.is_active:
            self._stream.stop()
        event.accept()
