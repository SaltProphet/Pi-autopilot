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

echo "Pi-Autopilot Setup Script"
echo "========================="
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run with sudo"
    echo "Usage: sudo bash installer/setup_pi.sh"
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
    echo "Example: sudo bash installer/setup_pi.sh"
    exit 1
fi

REAL_USER_HOME=$(eval echo "~$REAL_USER")

echo "Detected user: $REAL_USER"
echo "User home directory: $REAL_USER_HOME"
echo ""

echo "Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv git

echo "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

if [ ! -d ".git" ]; then
    echo "Validating SSH configuration..."
    echo ""
    
    # Check if SSH key exists
    SSH_KEY_FOUND=false
    for key_type in id_rsa id_ed25519 id_ecdsa id_dsa; do
        if [ -f "$REAL_USER_HOME/.ssh/$key_type" ]; then
            SSH_KEY_FOUND=true
            echo "✓ Found SSH key: $REAL_USER_HOME/.ssh/$key_type"
            break
        fi
    done
    
    if [ "$SSH_KEY_FOUND" = false ]; then
        echo "ERROR: No SSH keys found for user $REAL_USER"
        echo ""
        echo "SSH keys are required to clone the repository."
        echo ""
        echo "To set up SSH keys:"
        echo "  1. Generate an SSH key:"
        echo "     ssh-keygen -t ed25519 -C \"your_email@example.com\""
        echo ""
        echo "  2. Add the public key to your GitHub account:"
        echo "     cat ~/.ssh/id_ed25519.pub"
        echo "     Then go to: https://github.com/settings/keys"
        echo ""
        echo "  3. Re-run this installer"
        echo ""
        echo "For detailed instructions, see:"
        echo "  https://docs.github.com/en/authentication/connecting-to-github-with-ssh"
        echo ""
        echo "Alternative: Use HTTPS with Personal Access Token (PAT)"
        echo "  Run: sudo bash installer/setup_with_https.sh"
        exit 1
    fi
    
    # Test SSH connection to GitHub
    echo ""
    echo "Testing SSH connection to GitHub..."
    if sudo -u "$REAL_USER" ssh -T -o StrictHostKeyChecking=accept-new -o BatchMode=yes git@github.com 2>&1 | grep -q "successfully authenticated"; then
        echo "✓ SSH connection to GitHub successful"
    else
        echo "ERROR: SSH authentication to GitHub failed"
        echo ""
        echo "Your SSH key exists but GitHub authentication failed."
        echo ""
        echo "Possible causes:"
        echo "  1. SSH key not added to your GitHub account"
        echo "  2. SSH key has a passphrase and ssh-agent is not running"
        echo "  3. Wrong SSH key is being used"
        echo ""
        echo "To fix this:"
        echo "  1. Copy your PUBLIC key:"
        echo "     cat $REAL_USER_HOME/.ssh/id_ed25519.pub"
        echo "     (or cat $REAL_USER_HOME/.ssh/id_rsa.pub)"
        echo ""
        echo "  2. Add it to GitHub at: https://github.com/settings/keys"
        echo ""
        echo "  3. Test the connection manually:"
        echo "     ssh -T git@github.com"
        echo ""
        echo "  4. Re-run this installer"
        echo ""
        echo "For help, see:"
        echo "  https://docs.github.com/en/authentication/connecting-to-github-with-ssh"
        exit 1
    fi
    
    echo ""
    echo "Cloning repository via SSH..."
    # Clone as the actual user to use their SSH keys
    if ! sudo -u "$REAL_USER" git clone git@github.com:SaltProphet/Pi-autopilot.git . 2>&1; then
        echo ""
        echo "ERROR: Failed to clone repository"
        echo ""
        echo "This usually happens if:"
        echo "  - You don't have access to the repository"
        echo "  - Network connectivity issues"
        echo "  - SSH key permissions are wrong"
        echo ""
        echo "Try cloning manually to diagnose:"
        echo "  git clone git@github.com:SaltProphet/Pi-autopilot.git /tmp/test-clone"
        exit 1
    fi
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
cp "$INSTALL_DIR/saltprophet.service" /etc/systemd/system/pi-autopilot.service
chmod 644 /etc/systemd/system/pi-autopilot.service

echo "Setting up systemd timer..."
cp "$INSTALL_DIR/saltprophet.timer" /etc/systemd/system/pi-autopilot.timer
chmod 644 /etc/systemd/system/pi-autopilot.timer

echo "Setting up systemd service for dashboard..."
cp "$INSTALL_DIR/pi-autopilot-dashboard.service" /etc/systemd/system/
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
