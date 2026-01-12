#!/bin/bash
set -e

echo "=== Installing Pi-Autopilot Dashboard ==="

# Install systemd service for dashboard
echo "[1/3] Installing dashboard systemd service..."
sudo cp pi-autopilot-dashboard.service /etc/systemd/system/

echo "[2/3] Installing systemd timer for pipeline..."
sudo cp saltprophet.timer /etc/systemd/system/

# Reload systemd
echo "[3/3] Reloading systemd and enabling services..."
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable pi-autopilot.service
sudo systemctl enable pi-autopilot-dashboard.service
sudo systemctl enable pi-autopilot.timer

echo ""
echo "✅ Dashboard installation complete!"
echo ""
echo "Next steps:"
echo "1. Start the dashboard:    sudo systemctl start pi-autopilot-dashboard"
echo "2. Check dashboard status: sudo systemctl status pi-autopilot-dashboard"
echo "3. View logs:              journalctl -fu pi-autopilot-dashboard"
echo "4. Access dashboard:       http://<pi-ip>:8000"
echo ""
echo "Pipeline timer:"
echo "1. Start timer:            sudo systemctl start pi-autopilot.timer"
echo "2. Check next run:         systemctl list-timers pi-autopilot.timer"
echo "3. View logs:              journalctl -fu pi-autopilot"
echo ""
