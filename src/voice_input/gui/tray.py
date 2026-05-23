from __future__ import annotations

import logging

from voice_input.config import AppConfig

logger = logging.getLogger(__name__)


class TrayApp:
    def __init__(self, config: AppConfig | None = None, engine=None):
        self._config = config or AppConfig()
        self._engine = engine
        self._app = None
        self._tray = None

    def run(self) -> None:
        try:
            self._run_qt()
        except ImportError:
            logger.warning("PyQt6 not installed, GUI not available")
            self._run_console()

    def _run_qt(self) -> None:
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

        self._app = QApplication([])
        self._app.setQuitOnLastWindowClosed(False)

        self._tray = QSystemTrayIcon()
        self._tray.setToolTip("语音输入法")
        self._tray.setIcon(self._get_icon())

        menu = QMenu()

        toggle_action = QAction("开始录音", menu)
        toggle_action.triggered.connect(self._on_toggle)
        menu.addAction(toggle_action)

        menu.addSeparator()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self._app.quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.show()

        logger.info("System tray started")
        self._app.exec()

    def _run_console(self) -> None:
        import time

        logger.info("Running in console mode. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")

    def _on_toggle(self) -> None:
        if self._engine:
            if self._engine.is_recording:
                self._engine.stop_and_recognize()
            else:
                self._engine.start_recording()

    def _get_icon(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QColor(76, 175, 80))
        painter.setPen(Qt.PenStyle.NoPen)

        from PyQt6.QtCore import QRectF
        painter.drawEllipse(QRectF(4, 4, 56, 56))

        painter.setBrush(QColor(255, 255, 255))
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPolygonF
        triangle = QPolygonF([
            QPointF(22, 18),
            QPointF(46, 32),
            QPointF(22, 46),
        ])
        painter.drawPolygon(triangle)

        painter.end()

        return QIcon(pixmap)

    def update_status(self, recording: bool) -> None:
        if self._tray:
            self._tray.setToolTip("语音输入法 - 录音中..." if recording else "语音输入法")
