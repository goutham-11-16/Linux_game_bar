"""Integration tests for SingleInstanceManager IPC."""

import time
from pathlib import Path
from linux_game_bar.single_instance import SingleInstanceManager


def test_single_instance_toggle_ipc(qapp, tmp_path):
    sock_path = str(tmp_path / "test_ipc.sock")

    server_mgr = SingleInstanceManager()
    server_mgr.socket_path = sock_path

    toggle_received = []
    server_mgr.toggle_requested.connect(lambda: toggle_received.append(True))

    assert server_mgr.start_server() is True

    # Temporarily override get_socket_path for client
    from linux_game_bar import single_instance
    orig_fn = single_instance.get_socket_path
    single_instance.get_socket_path = lambda: sock_path

    try:
        # Send toggle from client
        res = SingleInstanceManager.send_command("toggle", timeout_ms=500)
        assert res is True

        # Process Qt events so server receives connection
        qapp.processEvents()
        time.sleep(0.1)
        qapp.processEvents()

        assert len(toggle_received) == 1
    finally:
        single_instance.get_socket_path = orig_fn
        server_mgr.cleanup()
        qapp.processEvents()
