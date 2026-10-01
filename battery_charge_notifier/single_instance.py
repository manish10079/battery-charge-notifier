"""Single-instance gate built on ``QLocalServer``/``QLocalSocket``.

The first launch claims a named local socket. Later launches fail to connect,
so instead of competing they hand a short command to the running instance (by
default: "open your settings") and exit. This keeps exactly one monitor, one
tray icon and one set of warnings alive per user session.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)

#: Commands understood by :class:`SingleInstance`'s ``messageReceived`` signal.
COMMAND_SHOW_SETTINGS = "show-settings"
COMMAND_PING = "ping"

CONNECT_TIMEOUT_MS = 500
PROBE_TIMEOUT_MS = 500
SERVER_NAME_TEMPLATE = "battery-charge-notifier-{user}"


def default_server_name() -> str:
    """Return a socket name unique to the current user.

    Including the user name keeps two people logged into the same machine (for
    example over fast user switching) from blocking one another.
    """
    try:
        user = os.getlogin()
    except OSError:  # pragma: no cover - depends on the host environment
        user = os.environ.get("USERNAME") or os.environ.get("USER") or "default"
    return SERVER_NAME_TEMPLATE.format(user=user)


class SingleInstance(QObject):
    """Owns the inter-process lock for one application instance."""

    #: Emitted with the raw command string sent by a later launch.
    messageReceived = Signal(str)

    def __init__(self, name: str | None = None, parent: QObject | None = None) -> None:
        """Create the gate.

        Args:
            name: Socket name. Defaults to :func:`default_server_name`.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._name = name or default_server_name()
        self._server: QLocalServer | None = None

    @property
    def name(self) -> str:
        """The socket name used by this gate."""
        return self._name

    @property
    def is_primary(self) -> bool:
        """Whether this process successfully claimed the lock."""
        return self._server is not None and self._server.isListening()

    def try_acquire(self) -> bool:
        """Attempt to become the primary instance.

        A live instance is detected by *connecting* to the name first. Only when
        nobody answers is the name treated as stale and cleared; a crashed
        process must not block startup forever, but neither may a second
        instance displace one that is still running.

        Returns:
            ``True`` when this process is the primary instance.
        """
        if self.is_primary:
            return True

        if self._has_live_listener():
            logger.info("Another instance already owns the socket %r", self._name)
            return False

        # Nobody is listening: any socket with this name is left over from a
        # process that died without cleaning up.
        QLocalServer.removeServer(self._name)

        server = QLocalServer(self)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(self._name):
            logger.warning(
                "Could not claim the single-instance socket %r: %s",
                self._name,
                server.errorString(),
            )
            server.deleteLater()
            return False

        self._server = server
        self._server.newConnection.connect(self._on_new_connection)
        logger.info("Claimed single-instance socket %r", self._name)
        return True

    def _has_live_listener(self) -> bool:
        """Return whether another process is currently serving :attr:`name`."""
        probe = QLocalSocket(self)
        probe.connectToServer(self._name)
        if not probe.waitForConnected(PROBE_TIMEOUT_MS):
            return False
        # Announce ourselves as a probe so the owner does not act on it.
        probe.write(f"{COMMAND_PING}\n".encode("utf-8"))
        probe.flush()
        probe.waitForBytesWritten(PROBE_TIMEOUT_MS)
        probe.disconnectFromServer()
        return True

    def notify_running_instance(self, message: str = COMMAND_SHOW_SETTINGS) -> bool:
        """Send *message* to the already-running instance.

        Returns:
            ``True`` when the message was written to another instance's socket.
        """
        socket = QLocalSocket(self)
        socket.connectToServer(self._name)
        if not socket.waitForConnected(CONNECT_TIMEOUT_MS):
            logger.debug("No running instance answered on %r", self._name)
            return False

        socket.write(f"{message}\n".encode("utf-8"))
        socket.flush()
        socket.waitForBytesWritten(CONNECT_TIMEOUT_MS)
        socket.disconnectFromServer()
        return True

    def release(self) -> None:
        """Release the lock so a later launch can claim it."""
        if self._server is None:
            return
        self._server.close()
        QLocalServer.removeServer(self._name)
        self._server = None

    # -- internals ---------------------------------------------------------
    def _on_new_connection(self) -> None:
        """Read one command from a connecting peer and relay it as a signal."""
        if self._server is None:
            return

        connection = self._server.nextPendingConnection()
        if connection is None:
            return

        connection.readyRead.connect(lambda: self._read_command(connection))
        connection.disconnected.connect(connection.deleteLater)
        # A peer that connects and immediately closes still needs servicing.
        if connection.canReadLine():
            self._read_command(connection)

    def _read_command(self, connection: QLocalSocket) -> None:
        """Emit the user command carried by *connection*."""
        payload = bytes(connection.readLine()).decode("utf-8", errors="replace").strip()
        if payload and payload != COMMAND_PING:
            # COMMAND_PING is the liveness handshake from try_acquire, not a
            # command, so it is deliberately not surfaced.
            logger.info("Received command from another launch: %r", payload)
            self.messageReceived.emit(payload)
        connection.disconnectFromServer()


__all__ = [
    "COMMAND_PING",
    "COMMAND_SHOW_SETTINGS",
    "SingleInstance",
    "default_server_name",
]
