import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import { Workspace } from 'resource:///org/gnome/shell/ui/workspace.js';
import Shell from 'gi://Shell';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';

const DBUS_IFACE = `
<node>
  <interface name="org.gnome.Shell.Extensions.LinuxGameBar">
    <method name="Toggle">
      <arg type="b" direction="out" name="success"/>
    </method>
    <method name="Show">
      <arg type="b" direction="out" name="success"/>
    </method>
    <method name="Hide">
      <arg type="b" direction="out" name="success"/>
    </method>
    <method name="Screenshot">
      <arg type="b" direction="out" name="success"/>
    </method>
  </interface>
</node>`;

export default class LinuxGameBarExtension extends Extension {
    enable() {
        console.log('[LinuxGameBarExtension] Enabling native OS compositor integration...');

        // 1. Export D-Bus Service
        this._dbusImpl = Gio.DBusExportedObject.wrapJSObject(DBUS_IFACE, this);
        try {
            this._dbusImpl.export(Gio.DBus.session, '/org/gnome/Shell/Extensions/LinuxGameBar');
        } catch (e) {
            console.error('[LinuxGameBarExtension] Failed to export DBus interface:', e);
        }

        // 2. Register Compositor-Level Keybindings via Mutter
        // Handled directly inside Mutter compositor, which completely suppresses the Super overlay key (Activities Overview / Recents)
        try {
            this._settings = this.getSettings();
            Main.wm.addKeybinding(
                'toggle-game-bar',
                this._settings,
                Meta.KeyBindingFlags.IGNORE_AUTOREPEAT,
                Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW | Shell.ActionMode.FULLSCREEN,
                () => {
                    this.Toggle();
                }
            );

            Main.wm.addKeybinding(
                'take-screenshot',
                this._settings,
                Meta.KeyBindingFlags.IGNORE_AUTOREPEAT,
                Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW | Shell.ActionMode.FULLSCREEN,
                () => {
                    this.Screenshot();
                }
            );
            console.log('[LinuxGameBarExtension] Compositor keybindings registered: Super+G and Super+Alt+Print');
        } catch (e) {
            console.error('[LinuxGameBarExtension] Failed to register compositor keybindings:', e);
        }

        // 3. Exclude Linux Game Bar from Activities Overview ("Recents") & App Switchers
        this._patchWorkspaceOverview();

        // 4. Hook Window Creation to mark Game Bar as an OS Overlay (Skip taskbar, stick across workspaces, keep above)
        this._setupWindowMasking();
    }

    disable() {
        console.log('[LinuxGameBarExtension] Disabling Linux Game Bar extension...');

        // Remove compositor keybindings
        try {
            Main.wm.removeKeybinding('toggle-game-bar');
            Main.wm.removeKeybinding('take-screenshot');
        } catch (e) {}
        this._settings = null;

        // Restore Workspace prototype hooks
        if (this._origIsOverviewWindow) {
            Workspace.prototype._isOverviewWindow = this._origIsOverviewWindow;
            this._origIsOverviewWindow = null;
        }
        if (this._origIsMyWindow) {
            Workspace.prototype._isMyWindow = this._origIsMyWindow;
            this._origIsMyWindow = null;
        }

        // Disconnect window created listener
        if (this._windowCreatedId && global.display) {
            global.display.disconnect(this._windowCreatedId);
            this._windowCreatedId = 0;
        }

        // Unexport DBus
        if (this._dbusImpl) {
            this._dbusImpl.unexport();
            this._dbusImpl = null;
        }
    }

    // -------------------------------------------------------------
    // DBus & Action Handlers
    // -------------------------------------------------------------
    Toggle() {
        this._sendSocketCommand('toggle');
        return true;
    }

    Show() {
        this._sendSocketCommand('show');
        return true;
    }

    Hide() {
        this._sendSocketCommand('hide');
        return true;
    }

    Screenshot() {
        this._sendSocketCommand('screenshot');
        return true;
    }

    // -------------------------------------------------------------
    // Direct UNIX Socket IPC (Zero Process Overhead)
    // -------------------------------------------------------------
    _sendSocketCommand(cmd) {
        try {
            let runtimeDir = GLib.getenv('XDG_RUNTIME_DIR') || `/run/user/${GLib.get_user_id ? GLib.get_user_id() : '1000'}`;
            let sockPath = `${runtimeDir}/linux-game-bar.sock`;

            if (GLib.file_test(sockPath, GLib.FileTest.EXISTS)) {
                let client = new Gio.SocketClient();
                let addr = Gio.UnixSocketAddress.new(sockPath);

                client.connect_async(addr, null, (source, res) => {
                    try {
                        let conn = source.connect_finish(res);
                        let outStream = conn.get_output_stream();
                        let msg = new TextEncoder().encode(cmd + '\n');
                        outStream.write_bytes_async(new GLib.Bytes(msg), GLib.PRIORITY_DEFAULT, null, (s, r) => {
                            try {
                                s.write_bytes_finish(r);
                                conn.close(null);
                            } catch (e) {}
                        });
                    } catch (e) {
                        this._fallbackRunCmd(cmd);
                    }
                });
                return;
            }
        } catch (e) {
            console.error('[LinuxGameBarExtension] Error writing to IPC socket:', e);
        }

        this._fallbackRunCmd(cmd);
    }

    _fallbackRunCmd(cmd) {
        let binPath = GLib.get_home_dir() + '/.local/bin/linux-game-bar';
        let bin = GLib.file_test(binPath, GLib.FileTest.IS_EXECUTABLE) ? binPath : 'linux-game-bar';
        this._runCmd([bin, '--' + cmd]);
    }

    _runCmd(args) {
        try {
            let proc = new Gio.Subprocess({
                argv: args,
                flags: Gio.SubprocessFlags.NONE,
            });
            proc.init(null);
        } catch (e) {
            console.error('[LinuxGameBarExtension] Error executing cmd:', e);
        }
    }

    // -------------------------------------------------------------
    // OS Window Masking & Overview Suppression
    // -------------------------------------------------------------
    _isGameBarWindow(metaWin) {
        if (!metaWin) return false;
        try {
            let wmClass = metaWin.get_wm_class ? metaWin.get_wm_class() : '';
            let title = metaWin.get_title ? metaWin.get_title() : '';
            let gtkApp = metaWin.get_gtk_application_id ? metaWin.get_gtk_application_id() : '';

            if (wmClass && (wmClass.toLowerCase().includes('linux-game-bar') || wmClass.toLowerCase().includes('gamebar') || wmClass === 'linux_game_bar')) {
                return true;
            }
            if (title && (title.includes('Linux Game Bar') || title === 'WidgetBase')) {
                return true;
            }
            if (gtkApp && gtkApp.toLowerCase().includes('linux-game-bar')) {
                return true;
            }
        } catch (e) {}
        return false;
    }

    _patchWorkspaceOverview() {
        const self = this;
        this._origIsOverviewWindow = Workspace.prototype._isOverviewWindow;
        Workspace.prototype._isOverviewWindow = function(window) {
            if (self._isGameBarWindow(window)) {
                return false;
            }
            return self._origIsOverviewWindow.call(this, window);
        };

        this._origIsMyWindow = Workspace.prototype._isMyWindow;
        Workspace.prototype._isMyWindow = function(window) {
            if (self._isGameBarWindow(window)) {
                return false;
            }
            return self._origIsMyWindow.call(this, window);
        };
    }

    _setupWindowMasking() {
        const self = this;
        this._windowCreatedId = global.display.connect('window-created', (display, window) => {
            if (self._isGameBarWindow(window)) {
                self._maskGameBarWindow(window);
            }
        });

        // Also mask any currently existing Game Bar windows
        try {
            for (const actor of global.get_window_actors()) {
                const metaWin = actor.meta_window;
                if (this._isGameBarWindow(metaWin)) {
                    this._maskGameBarWindow(metaWin);
                }
            }
        } catch (e) {}
    }

    _maskGameBarWindow(metaWin) {
        if (!metaWin) return;
        try {
            // 1. Mark skip-taskbar so window switcher (Alt+Tab) and overview exclude it
            try {
                Object.defineProperty(metaWin, 'skip_taskbar', {
                    get: () => true,
                    configurable: true,
                });
            } catch (e) {}

            if (metaWin.is_skip_taskbar) {
                metaWin.is_skip_taskbar = () => true;
            }

            // 2. Stick across all workspaces
            if (metaWin.stick) {
                metaWin.stick();
            }

            // 3. Keep above regular windows
            if (metaWin.make_above) {
                metaWin.make_above();
            }

            console.log('[LinuxGameBarExtension] Successfully masked window as OS overlay:', metaWin.get_title ? metaWin.get_title() : 'GameBar');
        } catch (e) {
            console.error('[LinuxGameBarExtension] Error masking window:', e);
        }
    }
}
