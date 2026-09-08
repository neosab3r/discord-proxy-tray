"""One tray instance — forward SHOW_PANEL / TAKEOVER for relaunch."""

from __future__ import annotations

import logging
import sys
import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

log = logging.getLogger(__name__)

INSTANCE_KEY = "discord-proxy-tray-v1"
TAKEOVER = "TAKEOVER"
SHOW_PANEL = "SHOW_PANEL"


class InstanceGuard(QObject):
    message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._server: QLocalServer | None = None

    def acquire(self) -> bool:
        """Return True if this process should run the tray."""
        if "--takeover" in sys.argv:
            return self._takeover_running_instance()
        return self._try_listen_or_forward()

    def release(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        QLocalServer.removeServer(INSTANCE_KEY)

    def _try_listen_or_forward(self) -> bool:
        sock = QLocalSocket()
        sock.connectToServer(INSTANCE_KEY)
        if sock.waitForConnected(400):
            cmd = SHOW_PANEL
            sock.write(cmd.encode("utf-8"))
            sock.waitForBytesWritten(1500)
            sock.disconnectFromServer()
            log.info("forwarded %s to running instance", cmd)
            return False
        return self._listen()

    def _takeover_running_instance(self) -> bool:
        # Retry connect — elevated pythonw may start before old tray binds the socket.
        for _ in range(60):
            sock = QLocalSocket()
            sock.connectToServer(INSTANCE_KEY)
            if sock.waitForConnected(400):
                log.info("elevated relaunch — requesting takeover")
                sock.write(TAKEOVER.encode("utf-8"))
                sock.waitForBytesWritten(2000)
                sock.disconnectFromServer()
                for attempt in range(60):
                    if self._listen():
                        log.info("takeover acquired after %s ms", attempt * 100)
                        return True
                    time.sleep(0.1)
                log.error("takeover timed out waiting for previous instance to release")
                return False
            time.sleep(0.1)
        log.info("no previous instance found — starting elevated tray")
        return self._listen()

    def _listen(self) -> bool:
        QLocalServer.removeServer(INSTANCE_KEY)
        server = QLocalServer(self)
        if not server.listen(INSTANCE_KEY):
            return False
        server.newConnection.connect(self._on_connection)
        self._server = server
        return True

    def _on_connection(self) -> None:
        if self._server is None:
            return
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        if socket.waitForReadyRead(1500):
            raw = bytes(socket.readAll()).decode("utf-8", errors="replace").strip()
            cmd = raw or SHOW_PANEL
            log.info("instance command: %s", cmd)
            self.message.emit(cmd)
        socket.disconnectFromServer()
