#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY=/usr/local/bin/wifi-switch
SERVICE=/etc/systemd/system/wifi-switch.service

echo "Installing wifi-switch..."

# Copy daemon (shebang already present in wifi_switch.py)
sudo install -m 755 "$SCRIPT_DIR/wifi_switch.py" "$BINARY"

# Install service
sudo install -m 644 "$SCRIPT_DIR/wifi-switch.service" "$SERVICE"

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable wifi-switch
sudo systemctl restart wifi-switch

echo "Done. Check status with: journalctl -u wifi-switch -f"
