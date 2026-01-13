#!/bin/bash

set -e

# Cleanup handler for partial installations if an error occurs
cleanup() {
    echo "An error occurred during setup. Attempting to clean up partial installation..." >&2

    # Only remove the installation directory if it is set and exists
    if [ -n "$INSTALL_DIR" ] && [ -d "$INSTALL_DIR" ]; then
        echo "Removing installation directory: $INSTALL_DIR" >&2
        rm -rf "$INSTALL_DIR"
    fi
}

# Run cleanup on any error
trap 'cleanup' ERR
INSTALL_DIR="/opt/pi-autopilot"

# Cleanup handler for partial installations if an error occurs
cleanup() {
    echo "An error occurred during setup. Attempting to clean up partial installation..." >&2

    # Only remove the installation directory if it is set and exists
    if [ -n "$INSTALL_DIR" ] && [ -d "$INSTALL_DIR" ]; then
        echo "Removing installation directory: $INSTALL_DIR" >&2
        rm -rf "$INSTALL_DIR"
    fi
}

# Run cleanup on any error
trap 'cleanup' ERR

echo "Pi-Autopilot Setup Script"
echo "========================="

if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo"
    exit 1
fi

echo "Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv git

echo "Creating installation directory: $INSTALL_DIR"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

if [ ! -d ".git" ]; then
    echo "Cloning repository..."
    git clone git@github.com:SaltProphet/Pi-autopilot.git .
fi

echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Creating data directories..."
mkdir -p data/artifacts data/artifacts/backups

# Set restrictive permissions on sensitive files
echo "Enforcing file permissions..."
chmod 600 .env 2>/dev/null || true
chmod 600 data/pipeline.db 2>/dev/null || true
chmod 700 data
chmod 700 data/artifacts
chmod 700 data/artifacts/backups

if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    chmod 600 .env
    echo ""
    echo "IMPORTANT: Edit /opt/pi-autopilot/.env with your API keys"
    echo ""
fi

echo "Setting up systemd service for pipeline..."
cp $INSTALL_DIR/saltprophet.service /etc/systemd/system/pi-autopilot.service
chmod 644 /etc/systemd/system/pi-autopilot.service

echo "Setting up systemd timer..."
cp $INSTALL_DIR/saltprophet.timer /etc/systemd/system/pi-autopilot.timer
chmod 644 /etc/systemd/system/pi-autopilot.timer

echo "Setting up systemd service for dashboard..."
cp $INSTALL_DIR/pi-autopilot-dashboard.service /etc/systemd/system/
chmod 644 /etc/systemd/system/pi-autopilot-dashboard.service

systemctl daemon-reload
systemctl enable pi-autopilot.service
systemctl enable pi-autopilot.timer
systemctl enable pi-autopilot-dashboard.service

echo "Starting services..."
systemctl start pi-autopilot-dashboard.service
systemctl start pi-autopilot.timer

echo "Setting up daily backup cron job..."
cat > /etc/cron.d/pi-autopilot-backup << 'EOF'
# Run backups daily at 2 AM
0 2 * * * root cd /opt/pi-autopilot && /opt/pi-autopilot/venv/bin/python -c "from services.backup_manager import BackupManager; BackupManager('./data/pipeline.db').backup_database(); BackupManager('./data/pipeline.db').cleanup_old_backups()" >> /var/log/pi-autopilot-backup.log 2>&1
EOF
chmod 644 /etc/cron.d/pi-autopilot-backup

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit /opt/pi-autopilot/.env with your API keys"
echo "2. Test run: systemctl start pi-autopilot.service"
echo "3. Check timer: systemctl status pi-autopilot.timer"
echo "4. Access dashboard: http://<your-pi-ip>:8000"
echo ""
echo "Useful commands:"
echo "  • View pipeline logs:  journalctl -fu pi-autopilot.service"
echo "  • View dashboard logs: journalctl -fu pi-autopilot-dashboard.service"
echo "  • Check next timer run: systemctl list-timers pi-autopilot.timer"
echo "  • Edit timer schedule: systemctl edit pi-autopilot.timer"
echo ""
echo "See docs/MONITORING.md for detailed monitoring instructions"
