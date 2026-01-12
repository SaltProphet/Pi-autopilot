#!/bin/bash
set -e

echo "=== Setting up Pi-Autopilot Monitoring & Alerting ==="

INSTALL_DIR="${1:-.}"
DASHBOARD_PORT="${2:-8000}"

# Create systemd service override for dashboard
mkdir -p /etc/systemd/system/pi-autopilot-dashboard.service.d

cat > /etc/systemd/system/pi-autopilot-dashboard.service.d/override.conf << EOF
[Service]
# Bind to specific port
Environment="DASHBOARD_PORT=$DASHBOARD_PORT"
EOF

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo "✅ Monitoring setup complete!"
echo ""
echo "Access the dashboard at: http://<your-pi-ip>:$DASHBOARD_PORT"
echo ""
echo "Features:"
echo "  • Real-time cost tracking (lifetime + last 24h)"
echo "  • Pipeline stage breakdown (completed/discarded/rejected/failed)"
echo "  • Active posts monitoring"
echo "  • Recent activity feed"
echo "  • Cost limit warnings"
echo ""
