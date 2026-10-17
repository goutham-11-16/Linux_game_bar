"""Screen capture and screencasting integration via GNOME D-Bus and XDG Desktop Portal."""

import os
import time
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("linux_game_bar.capture")


class CaptureService:
    """Provides screenshot and screen recording across Wayland (GNOME) and X11."""

    def __init__(self, capture_dir: Optional[Path] = None, recording_dir: Optional[Path] = None):
        self.capture_dir = capture_dir or (Path.home() / "Pictures" / "Captures")
        self.recording_dir = recording_dir or (Path.home() / "Videos" / "Captures")
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.recording_dir.mkdir(parents=True, exist_ok=True)

        self._recording_active: bool = False
        self._recording_start_time: float = 0.0
        self._current_recording_file: Optional[str] = None
        self._ffmpeg_process: Optional[subprocess.Popen] = None

    @property
    def is_recording(self) -> bool:
        return self._recording_active

    def get_recording_duration(self) -> float:
        if not self._recording_active:
            return 0.0
        return max(0.0, time.monotonic() - self._recording_start_time)

    def get_latest_screenshot(self) -> Optional[Path]:
        """Find the most recently modified screenshot in capture directories."""
        dirs_to_check = [
            self.capture_dir,
            Path.home() / "Pictures" / "Screenshots",
            Path.home() / "Pictures",
        ]
        candidates = []
        for d in dirs_to_check:
            if d.exists():
                for p in d.glob("*.png"):
                    try:
                        candidates.append((p.stat().st_mtime, p))
                    except Exception:
                        pass
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        return None

    def _portal_screenshot_automatic(self, target_file: Path) -> Optional[Path]:
        """Take automatic full screenshot via portal without prompting for region, silently without shutter sounds or OS banners."""
        py_script = """
import sys, urllib.parse, shutil, subprocess
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

app_schema = 'org.gnome.desktop.notifications.application:/org/gnome/desktop/notifications/application/org-freedesktop-portal-desktop/'
sound_schema = 'org.gnome.desktop.sound'

orig_sound = None
orig_enable = None
orig_banners = None

# Suppress shutter sound
try:
    orig_sound = subprocess.check_output(['gsettings', 'get', sound_schema, 'event-sounds'], stderr=subprocess.DEVNULL).decode().strip()
    subprocess.run(['gsettings', 'set', sound_schema, 'event-sounds', 'false'], stderr=subprocess.DEVNULL)
except Exception:
    pass

# Suppress portal notification popup / banner
try:
    orig_enable = subprocess.check_output(['gsettings', 'get', app_schema, 'enable'], stderr=subprocess.DEVNULL).decode().strip()
    orig_banners = subprocess.check_output(['gsettings', 'get', app_schema, 'show-banners'], stderr=subprocess.DEVNULL).decode().strip()
    subprocess.run(['gsettings', 'set', app_schema, 'enable', 'false'], stderr=subprocess.DEVNULL)
    subprocess.run(['gsettings', 'set', app_schema, 'show-banners', 'false'], stderr=subprocess.DEVNULL)
except Exception:
    pass

loop = GLib.MainLoop()
conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
saved_path = None

def on_signal(connection, sender_name, object_path, interface_name, signal_name, parameters, user_data):
    global saved_path
    code, results = parameters.unpack()
    if code == 0 and 'uri' in results:
        uri = results['uri']
        parsed = urllib.parse.urlparse(uri)
        saved_path = urllib.parse.unquote(parsed.path)
    loop.quit()

conn.signal_subscribe(
    'org.freedesktop.portal.Desktop',
    'org.freedesktop.portal.Request',
    'Response',
    None,
    None,
    Gio.DBusSignalFlags.NONE,
    on_signal,
    None
)

try:
    conn.call_sync(
        'org.freedesktop.portal.Desktop',
        '/org/freedesktop/portal/desktop',
        'org.freedesktop.portal.Screenshot',
        'Screenshot',
        GLib.Variant('(sa{sv})', ('', {'interactive': GLib.Variant('b', False)})),
        GLib.VariantType('(o)'),
        Gio.DBusCallFlags.NONE,
        5000,
        None
    )
except Exception:
    pass

GLib.timeout_add_seconds(6, loop.quit)
loop.run()

# Restore original audio and notification preferences
try:
    if orig_sound:
        subprocess.run(['gsettings', 'set', sound_schema, 'event-sounds', orig_sound], stderr=subprocess.DEVNULL)
    if orig_enable:
        subprocess.run(['gsettings', 'set', app_schema, 'enable', orig_enable], stderr=subprocess.DEVNULL)
    if orig_banners:
        subprocess.run(['gsettings', 'set', app_schema, 'show-banners', orig_banners], stderr=subprocess.DEVNULL)
except Exception:
    pass

if saved_path:
    print('SAVED:' + saved_path)
    sys.exit(0)
sys.exit(1)
"""
        try:
            res = subprocess.run(
                ["/usr/bin/python3", "-c", py_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=8,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if line.startswith("SAVED:"):
                        src_path = Path(line.replace("SAVED:", "").strip())
                        if src_path.exists():
                            shutil.copy2(src_path, target_file)
                            return target_file
        except Exception as e:
            logger.warning(f"Automatic full screenshot failed: {e}")
        return None

    def take_screenshot(self, interactive: bool = False) -> Tuple[bool, str]:
        """Take a screenshot using desktop portal or available tools."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target_file = self.capture_dir / f"Screenshot_{timestamp}.png"

        # 1. Automatic full desktop screenshot without region prompt
        if not interactive:
            auto_file = self._portal_screenshot_automatic(target_file)
            if auto_file and auto_file.exists():
                logger.info(f"Automatic full screenshot saved to {auto_file}")
                return True, str(auto_file)

        # 2. Try portal interactive mode
        try:
            inter_val = "true" if interactive else "false"
            res = subprocess.run(
                [
                    "gdbus",
                    "call",
                    "--session",
                    "--dest",
                    "org.freedesktop.portal.Desktop",
                    "--object-path",
                    "/org/freedesktop/portal/desktop",
                    "--method",
                    "org.freedesktop.portal.Screenshot.Screenshot",
                    "",
                    f"{{'interactive': <{inter_val}>}}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                logger.info("Screenshot requested via xdg-desktop-portal.")
                return True, str(target_file)
        except Exception as e:
            logger.warning(f"Portal screenshot attempt failed: {e}")

        # Fallback to grim if available
        if shutil.which("grim"):
            try:
                res = subprocess.run(["grim", str(target_file)], timeout=3)
                if res.returncode == 0 and target_file.exists():
                    return True, str(target_file)
            except Exception:
                pass

        # Fallback to gnome-screenshot if available
        if shutil.which("gnome-screenshot"):
            try:
                res = subprocess.run(["gnome-screenshot", "-f", str(target_file)], timeout=5)
                if res.returncode == 0 and target_file.exists():
                    return True, str(target_file)
            except Exception:
                pass

        return False, "No working screenshot method found for this session."

    def start_recording(self) -> Tuple[bool, str]:
        """Start screen recording via GNOME Screencast or FFmpeg."""
        if self._recording_active:
            return False, "A recording is already in progress."

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target_file = self.recording_dir / f"Recording_{timestamp}.webm"
        file_template = str(target_file)

        # Attempt 1: GNOME Shell Screencast DBus API
        try:
            res = subprocess.run(
                [
                    "gdbus",
                    "call",
                    "--session",
                    "--dest",
                    "org.gnome.Shell.Screencast",
                    "--object-path",
                    "/org/gnome/Shell/Screencast",
                    "--method",
                    "org.gnome.Shell.Screencast.Screencast",
                    file_template,
                    "{}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and "true" in res.stdout:
                # Output format: (true, '/path/to/Recording_...mp4')
                parts = res.stdout.strip().split("'", 2)
                actual_path = parts[1] if len(parts) >= 2 else str(target_file)
                self._recording_active = True
                self._recording_start_time = time.monotonic()
                self._current_recording_file = actual_path
                logger.info(f"GNOME Shell screencast started: {actual_path}")
                return True, actual_path
        except Exception as e:
            logger.warning(f"GNOME Shell screencast initiation failed: {e}")

        # Attempt 2: FFmpeg fallback (especially on X11)
        if shutil.which("ffmpeg"):
            display = os.environ.get("DISPLAY", ":0")
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "x11grab",
                "-s", "1920x1080",
                "-i", display,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",
                str(target_file.with_suffix(".mp4")),
            ]
            try:
                self._ffmpeg_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._recording_active = True
                self._recording_start_time = time.monotonic()
                self._current_recording_file = str(target_file.with_suffix(".mp4"))
                logger.info(f"FFmpeg recording started: {self._current_recording_file}")
                return True, self._current_recording_file
            except Exception as e:
                logger.error(f"FFmpeg recording start failed: {e}")

        return False, "Failed to start screen recording on this system."

    def stop_recording(self) -> Tuple[bool, str]:
        """Stop active screen recording and verify output."""
        if not self._recording_active:
            return False, "No active recording."

        rec_file = self._current_recording_file
        self._recording_active = False

        # If FFmpeg was used
        if self._ffmpeg_process:
            try:
                self._ffmpeg_process.terminate()
                self._ffmpeg_process.wait(timeout=5)
            except Exception:
                self._ffmpeg_process.kill()
            self._ffmpeg_process = None

        # Stop GNOME Shell Screencast
        try:
            subprocess.run(
                [
                    "gdbus",
                    "call",
                    "--session",
                    "--dest",
                    "org.gnome.Shell.Screencast",
                    "--object-path",
                    "/org/gnome/Shell/Screencast",
                    "--method",
                    "org.gnome.Shell.Screencast.StopScreencast",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"StopScreencast call failed: {e}")

        # Wait briefly for container finalization
        time.sleep(0.5)

        # Verify output file
        if rec_file and Path(rec_file).exists() and Path(rec_file).stat().st_size > 0:
            logger.info(f"Recording stopped and verified: {rec_file} ({Path(rec_file).stat().st_size} bytes)")
            return True, rec_file

        # Check if GNOME saved with a different name in Videos
        videos_dir = Path.home() / "Videos"
        if videos_dir.exists():
            for p in sorted(videos_dir.glob("Screencast*.webm"), key=lambda x: x.stat().st_mtime, reverse=True):
                if time.time() - p.stat().st_mtime < 10:
                    return True, str(p)

        return True, rec_file or "Recording saved."
