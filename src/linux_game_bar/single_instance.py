"""Single instance manager and local IPC server using QLocalServer."""

import os
import sys
import logging
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger("linux_game_bar.ipc")


def get_socket_path() -> str:
    """Return standard socket path in XDG_RUNTIME_DIR or ~/.cache."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and os.path.exists(runtime_dir):
        return os.path.join(runtime_dir, "linux-game-bar.sock")

    cache_home = os.environ.get("XDG_CACHE_HOME")
    base = Path(cache_home) if cache_home else Path.home() / ".cache"
    sock_dir = base / "linux-game-bar"
    sock_dir.mkdir(parents=True, exist_ok=True)
    return str(sock_dir / "ipc.sock")


class SingleInstanceManager(QObject):
    """Ensures single running instance and listens for incoming commands."""

    toggle_requested = Signal()
    show_requested = Signal()
    hide_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self.server: QLocalServer = None
        self.socket_path = get_socket_path()

    @staticmethod
    def send_command(command: str = "toggle", timeout_ms: int = 1500) -> bool:
        """Attempt to send a command to an existing instance.

        Returns True if an existing instance received the command, False otherwise.
        """
        import socket
        sock_path = get_socket_path()
        if not os.path.exists(sock_path):
            return False

        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(max(0.1, timeout_ms / 1000.0))
            s.connect(sock_path)
            msg = (command.strip() + "\n").encode("utf-8")
            s.sendall(msg)
            try:
                _ = s.recv(128)
            except Exception:
                pass
            s.close()
            return True
        except Exception as e:
            logger.debug(f"Could not send IPC command to {sock_path}: {e}")
            return False

    def start_server(self) -> bool:
        """Start the local IPC server. Removes stale socket if needed."""
        # Try connecting first to verify if another instance is alive
        import socket
        if os.path.exists(self.socket_path):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(0.3)
                s.connect(self.socket_path)
                s.close()
                logger.warning("Another instance is already running.")
                return False
            except Exception:
                # Socket file exists but not responding -> stale socket
                try:
                    os.remove(self.socket_path)
                    logger.info(f"Cleaned up stale socket {self.socket_path}")
                except OSError as e:
                    logger.error(f"Failed to remove stale socket {self.socket_path}: {e}")

        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._on_new_connection)

        if not self.server.listen(self.socket_path):
            logger.error(f"Failed to start QLocalServer on {self.socket_path}: {self.server.errorString()}")
            return False

        logger.info(f"IPC server listening on {self.socket_path}")
        return True

    def _on_new_connection(self) -> None:
        """Handle incoming client connection."""
        while self.server.hasPendingConnections():
            client_socket = self.server.nextPendingConnection()
            if not client_socket:
                continue
            client_socket.setParent(self)

            if client_socket.bytesAvailable() > 0:
                self._handle_client_data(client_socket)
            else:
                client_socket.readyRead.connect(lambda s=client_socket: self._handle_client_data(s))

    def _handle_client_data(self, client_socket: QLocalSocket) -> None:
        """Read command from client and emit matching signal."""
        try:
            raw = client_socket.readAll().data()
            data = raw.decode("utf-8").strip().lower()
            if data:
                logger.info(f"Received IPC command: {data}")
                if data == "toggle":
                    self.toggle_requested.emit()
                elif data == "show":
                    self.show_requested.emit()
                elif data == "hide":
                    self.hide_requested.emit()
                elif data == "quit":
                    self.quit_requested.emit()
            client_socket.write(b"OK\n")
            client_socket.flush()
        except Exception as e:
            logger.error(f"Error processing IPC client data: {e}")
        finally:
            client_socket.disconnectFromServer()
            client_socket.deleteLater()

    def cleanup(self) -> None:
        """Stop server and clean up socket file."""
        if self.server:
            self.server.close()
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except Exception:
                pass
