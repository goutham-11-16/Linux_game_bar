#!/usr/bin/env bash
set -euo pipefail

SHORTCUT="${1:-<Super>g}"
NAME="Linux Game Bar"
CMD="${2:-linux-game-bar --toggle}"

echo "Configuring GNOME custom keybinding: $SHORTCUT -> $CMD"

if ! command -v gsettings >/dev/null 2>&1; then
    echo "Error: gsettings command not available."
    exit 1
fi

SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
KEY="custom-keybindings"
SUB_SCHEMA="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"

CURRENT=$(gsettings get "$SCHEMA" "$KEY")
echo "Current custom bindings: $CURRENT"

# Allocate slot
SLOT="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/linux-game-bar/"

# Update values
gsettings set "${SUB_SCHEMA}:${SLOT}" name "$NAME"
gsettings set "${SUB_SCHEMA}:${SLOT}" command "$CMD"
gsettings set "${SUB_SCHEMA}:${SLOT}" binding "$SHORTCUT"

# Add slot to list if not present
if [[ "$CURRENT" != *"$SLOT"* ]]; then
    if [ "$CURRENT" = "@as []" ] || [ "$CURRENT" = "[]" ]; then
        gsettings set "$SCHEMA" "$KEY" "['$SLOT']"
    else
        # Remove trailing bracket and append
        NEW_LIST=$(echo "$CURRENT" | sed "s/]/, '$SLOT']/")
        gsettings set "$SCHEMA" "$KEY" "$NEW_LIST"
    fi
fi

echo "Successfully registered $NAME with shortcut $SHORTCUT!"
