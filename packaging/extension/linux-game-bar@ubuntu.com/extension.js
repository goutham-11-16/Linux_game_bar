import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
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
  </interface>
</node>`;

export default class LinuxGameBarExtension extends Extension {
    enable() {
        this._dbusImpl = Gio.DBusExportedObject.wrapJSObject(DBUS_IFACE, this);
        try {
            this._dbusImpl.export(Gio.DBus.session, '/org/gnome/Shell/Extensions/LinuxGameBar');
        } catch (e) {
            console.error('[LinuxGameBarExtension] Failed to export DBus interface:', e);
        }
    }

    disable() {
        if (this._dbusImpl) {
            this._dbusImpl.unexport();
            this._dbusImpl = null;
        }
    }

    Toggle() {
        this._triggerToggle();
        return true;
    }

    Show() {
        this._runCmd(['linux-game-bar', '--show']);
        return true;
    }

    Hide() {
        this._runCmd(['linux-game-bar', '--hide']);
        return true;
    }

    _triggerToggle() {
        let binPath = GLib.get_home_dir() + '/.local/bin/linux-game-bar';
        if (GLib.file_test(binPath, GLib.FileTest.IS_EXECUTABLE)) {
            this._runCmd([binPath, '--toggle']);
        } else {
            this._runCmd(['linux-game-bar', '--toggle']);
        }
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
}
