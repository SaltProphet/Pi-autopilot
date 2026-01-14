#!/bin/bash

set -e

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

echo "Pi-Autopilot Setup Script (HTTPS Mode)"
echo "======================================="
echo ""
echo "This installer uses HTTPS with a Personal Access Token (PAT)"
echo "instead of SSH keys."
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run with sudo"
    echo "Usage: sudo bash installer/setup_with_https.sh"
    exit 1
fi

# Detect the actual user (not root)
if [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
else
    REAL_USER=$(logname 2>/dev/null || who am i | awk '{print $1}' || echo "")
fi

if [ -z "$REAL_USER" ] || [ "$REAL_USER" = "root" ]; then
    echo "ERROR: Could not detect the actual user."
    echo "Please run this script with sudo as a regular user, not as root directly."
    echo "Example: sudo bash installer/setup_with_https.sh"
    exit 1
fi

echo "Detected user: $REAL_USER"
echo ""

# Prompt for GitHub PAT
echo "You need a GitHub Personal Access Token (PAT) to clone the repository."
echo ""
echo "If you don't have one:"
echo "  1. Go to: https://github.com/settings/tokens"
echo "  2. Click 'Generate new token (classic)'"
echo "  3. Give it a name (e.g., 'Pi-Autopilot')"
echo "  4. Select scope: 'repo' (Full control of private repositories)"
echo "  5. Click 'Generate token'"
echo "  6. Copy the token (you won't be able to see it again!)"
echo ""
read -sp "Enter your GitHub Personal Access Token: " GITHUB_TOKEN
echo ""

if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: No token provided"
    exit 1
fi

# Validate token format (should be a long alphanumeric string)
if ! echo "$GITHUB_TOKEN" | grep -qE '^[a-zA-Z0-9_]{20,}$'; then
    echo "WARNING: Token format looks unusual. Proceeding anyway..."
fi

echo ""
echo "Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv git

echo "Creating installation directory: $INSTALL_DIR"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

if [ ! -d ".git" ]; then
    echo ""
    echo "Cloning repository via HTTPS..."
    
    # Clone using HTTPS with PAT (use git credential helper to avoid exposure)
    # Set up a temporary credential helper
    git config --global credential.helper 'cache --timeout=300'
    
    # Clone with the token - it will be cached temporarily
    if ! git clone https://${GITHUB_TOKEN}@github.com/SaltProphet/Pi-autopilot.git . 2>/dev/null; then
        # Clear the credential cache on failure
        git credential-cache exit 2>/dev/null || true
        # Clear the token from memory
        unset GITHUB_TOKEN
        
        echo ""
        echo "ERROR: Failed to clone repository"
        echo ""
        echo "Possible causes:"
        echo "  - Invalid or expired Personal Access Token"
        echo "  - Token doesn't have 'repo' scope"
        echo "  - You don't have access to the repository"
        echo "  - Network connectivity issues"
        echo ""
        echo "To fix:"
        echo "  1. Verify your token at: https://github.com/settings/tokens"
        echo "  2. Ensure it has 'repo' scope"
        echo "  3. Re-run this installer with a valid token"
        exit 1
    fi
    
    # Clear the credential cache after successful clone
    git credential-cache exit 2>/dev/null || true
    
    # Clear the token from memory for security
    unset GITHUB_TOKEN
    
    echo "✓ Repository cloned successfully"
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
echo "2. Test run: sudo systemctl start pi-autopilot.service"
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
echo ""
