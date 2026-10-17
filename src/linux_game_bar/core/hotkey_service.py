"""
Linux Global Hotkey Service matching Windows HotKeyService.cs.
Listens across system keyboards via evdev and triggers registered snippet callbacks.
"""

import os
import re
import select
import logging
import threading
from typing import Dict, Callable, Optional, Set, List

try:
    import evdev
    from evdev import ecodes
    HAS_EVDEV = True
except ImportError:
    HAS_EVDEV = False

logger = logging.getLogger("linux_game_bar.hotkey_service")


class GlobalHotKeyService:
    """
    Background hotkey listener that captures registered global shortcuts (e.g. F8, Ctrl+Alt+T)
    even when games or other applications have full focus on Linux.
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._registry: Dict[str, Callable[[], None]] = {}
        self._lock = threading.Lock()
        self._active_mods: Set[str] = set()
        self.is_paused = False

    def register(self, hotkey_str: str, callback: Callable[[], None]) -> bool:
        """
        Registers a hotkey string matching Windows format:
        e.g. "F8", "Control + Alt + T", "Control + Shift + D1", "F12"
        """
        if not hotkey_str or hotkey_str.strip().lower() in ("none", ""):
            return False

        norm_key = self.normalize_hotkey(hotkey_str)
        with self._lock:
            self._registry[norm_key] = callback
        logger.info(f"[HotKeyService] Registered global hotkey: '{hotkey_str}' (norm: '{norm_key}')")
        self.ensure_started()
        return True

    def unregister(self, hotkey_str: str) -> None:
        norm_key = self.normalize_hotkey(hotkey_str)
        with self._lock:
            self._registry.pop(norm_key, None)

    def unregister_all(self) -> None:
        with self._lock:
            self._registry.clear()

    @staticmethod
    def normalize_hotkey(hotkey_str: str) -> str:
        """
        Normalizes a hotkey string into a sorted, lowercase set of tokens.
        Example: "Control, Shift + F8" -> "ctrl+shift+f8"
        """
        parts = re.split(r"[\s\+\,]+", hotkey_str.strip().lower())
        mods = set()
        keys = []
        ascii_shift_digits = {
            "33": "1",  # !
            "64": "2",  # @
            "35": "3",  # #
            "36": "4",  # $
            "37": "5",  # %
            "94": "6",  # ^
            "38": "7",  # &
            "42": "8",  # *
            "40": "9",  # (
            "41": "0",  # )
        }

        for p in parts:
            if not p:
                continue
            if p in ("control", "ctrl"):
                mods.add("ctrl")
            elif p in ("shift",):
                mods.add("shift")
            elif p in ("alt", "menu"):
                mods.add("alt")
            elif p in ("windows", "win", "super"):
                mods.add("super")
            else:
                if p.startswith("key_"):
                    p = p[4:]
                if p in ("escape", "esc"):
                    keys.append("esc")
                elif p in ascii_shift_digits:
                    keys.append(ascii_shift_digits[p])
                elif p.startswith("d") and len(p) == 2 and p[1].isdigit():
                    keys.append(p[1])
                elif p.startswith("numpad") and len(p) == 7 and p[6].isdigit():
                    keys.append(p[6])
                else:
                    keys.append(p)

        sorted_parts = sorted(list(mods)) + sorted(keys)
        return "+".join(sorted_parts)

    def are_modifiers_held(self) -> bool:
        with self._lock:
            return len(self._active_mods) > 0

    def wait_for_modifiers_released(self, timeout_sec: float = 1.2) -> None:
        """Waits until user's fingers have released physical modifier keys (matching Windows InputService)."""
        import time
        start = time.time()
        while time.time() - start < timeout_sec:
            if not self.are_modifiers_held():
                break
            time.sleep(0.025)

    @staticmethod
    def release_modifiers() -> None:
        """Sends key-up events for modifier keys to clear state in compositor/uinput."""
        import subprocess
        socket_path = os.environ.get("YDOTOOL_SOCKET", "/tmp/.ydotool_socket")
        env = dict(os.environ)
        if os.path.exists(socket_path):
            env["YDOTOOL_SOCKET"] = socket_path
        subprocess.run(
            ["ydotool", "key", "29:0", "97:0", "42:0", "54:0", "56:0", "100:0", "125:0", "126:0"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def ensure_started(self) -> None:
        if not HAS_EVDEV:
            logger.warning("[HotKeyService] evdev not installed; background hotkeys disabled.")
            return

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._listener_loop, daemon=True, name="AutoTyperHotKeyThread")
        self._thread.start()
        logger.info("[HotKeyService] Started background global hotkey listener.")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.unregister_all()

    def _listener_loop(self) -> None:
        """Polls physical input keyboard devices for key combinations."""
        devices: List[evdev.InputDevice] = []
        try:
            for path in evdev.list_devices():
                try:
                    dev = evdev.InputDevice(path)
                    # Don't listen to virtual ydotool devices to avoid feedback loops!
                    if "ydotool" in dev.name.lower():
                        continue
                    caps = dev.capabilities()
                    if ecodes.EV_KEY in caps:
                        # Must have alphanumeric keys or function keys
                        key_caps = caps[ecodes.EV_KEY]
                        if ecodes.KEY_A in key_caps or ecodes.KEY_F1 in key_caps:
                            devices.append(dev)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"[HotKeyService] Failed enumerating evdev devices: {e}")
            return

        if not devices:
            logger.warning("[HotKeyService] No physical keyboard devices found for global hotkeys.")
            return

        active_keys: Set[str] = set()
        active_mods: Set[str] = set()

        key_name_map = {
            ecodes.KEY_LEFTCTRL: "ctrl",
            ecodes.KEY_RIGHTCTRL: "ctrl",
            ecodes.KEY_LEFTSHIFT: "shift",
            ecodes.KEY_RIGHTSHIFT: "shift",
            ecodes.KEY_LEFTALT: "alt",
            ecodes.KEY_RIGHTALT: "alt",
            ecodes.KEY_LEFTMETA: "super",
            ecodes.KEY_RIGHTMETA: "super",
        }

        # Build reverse map for common keys
        code_to_name: Dict[int, str] = {}
        for name, code in ecodes.__dict__.items():
            if name.startswith("KEY_"):
                k_name = name[4:].lower()
                code_to_name[code] = k_name

        fds = {dev.fd: dev for dev in devices}

        while self._running:
            try:
                r, _, _ = select.select(list(fds.keys()), [], [], 0.5)
                if not r:
                    continue

                for fd in r:
                    dev = fds[fd]
                    for event in dev.read():
                        if event.type != ecodes.EV_KEY:
                            continue

                        is_down = (event.value == 1)
                        is_up = (event.value == 0)
                        code = event.code

                        # Check modifier keys
                        if code in key_name_map:
                            mod = key_name_map[code]
                            if is_down:
                                active_mods.add(mod)
                            elif is_up:
                                active_mods.discard(mod)
                            with self._lock:
                                self._active_mods = set(active_mods)
                            continue

                        # Regular key
                        raw_name = code_to_name.get(code, "")
                        if not raw_name:
                            continue

                        if is_down:
                            # Build current combo string
                            curr_keys = [raw_name]
                            sorted_combo = sorted(list(active_mods)) + sorted(curr_keys)
                            combo_str = "+".join(sorted_combo)

                            if not self.is_paused:
                                with self._lock:
                                    callback = self._registry.get(combo_str)
                                if callback:
                                    logger.info(f"[HotKeyService] Global hotkey matched: '{combo_str}' -> Triggering callback!")
                                    try:
                                        callback()
                                    except Exception as ex:
                                        logger.error(f"[HotKeyService] Error executing hotkey callback: {ex}")

            except Exception as ex:
                if self._running:
                    logger.debug(f"[HotKeyService] Read cycle exception: {ex}")
                time.sleep(0.1)


# Global singleton instance
_hotkey_service_instance: Optional[GlobalHotKeyService] = None

def get_hotkey_service() -> GlobalHotKeyService:
    global _hotkey_service_instance
    if _hotkey_service_instance is None:
        _hotkey_service_instance = GlobalHotKeyService()
    return _hotkey_service_instance
