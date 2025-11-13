#!/bin/bash
# File: deployments/scripts/deploy_debian.sh
# MUTT v2.5 Debian Deployment Script

set -e

MUTT_USER="mutt"
MUTT_GROUP="mutt"
MUTT_HOME="/opt/mutt"
PYTHON_VERSION="3.10"

echo "=== MUTT v2.5 Debian Deployment ==="

# 1. Check Python 3.10 availability
if ! command -v python${PYTHON_VERSION} &> /dev/null; then
    echo "ERROR: Python ${PYTHON_VERSION} not found!"
    echo "Install it using:"
    echo "  sudo apt update"
    echo "  sudo apt install -y software-properties-common"
    echo "  sudo add-apt-repository ppa:deadsnakes/ppa"
    echo "  sudo apt update"
    echo "  sudo apt install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-venv"
    exit 1
fi

# 2. Create user and group
if ! id "$MUTT_USER" &>/dev/null; then
    echo "Creating mutt user..."
    sudo useradd --system --home-dir "$MUTT_HOME" --shell /bin/bash --create-home "$MUTT_USER"
fi

# 3. Create directories
echo "Creating directories..."
sudo mkdir -p "$MUTT_HOME"/{services,scripts,database,logs,venv}
sudo chown -R "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME"

# 4. Install Python dependencies
echo "Setting up Python virtual environment..."
sudo -u "$MUTT_USER" python${PYTHON_VERSION} -m venv "$MUTT_HOME/venv"
sudo -u "$MUTT_USER" "$MUTT_HOME/venv/bin/pip" install --upgrade pip
sudo -u "$MUTT_USER" "$MUTT_HOME/venv/bin/pip" install -r requirements.txt

# 5. Copy application files
echo "Copying application files..."
sudo cp -r services/* "$MUTT_HOME/services/"
sudo cp -r scripts/* "$MUTT_HOME/scripts/"
sudo cp -r database/* "$MUTT_HOME/database/"
sudo chown -R "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME"

# 6. Copy environment file
if [ ! -f "$MUTT_HOME/.env" ]; then
    echo "Creating .env file..."
    sudo cp .env.template "$MUTT_HOME/.env"
    sudo chown "$MUTT_USER:$MUTT_GROUP" "$MUTT_HOME/.env"
    sudo chmod 600 "$MUTT_HOME/.env"
    echo "WARNING: Edit $MUTT_HOME/.env with production values!"
fi

# 7. Install systemd service files
echo "Installing systemd services..."
sudo cp deployments/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# 8. Configure firewall (ufw)
echo "Configuring firewall..."
if command -v ufw &> /dev/null; then
    # Allow Web UI port
    sudo ufw allow 8090/tcp comment "MUTT Web UI"
    echo "Firewall rules added. Enable ufw with: sudo ufw enable"
else
    echo "WARNING: ufw not installed. Install with: sudo apt install ufw"
fi

# 9. Enable and start services
echo "Enabling services..."
sudo systemctl enable mutt-ingestor.service
sudo systemctl enable mutt-alerter@{1..5}.service
sudo systemctl enable mutt-moog-forwarder.service
sudo systemctl enable mutt-webui.service
sudo systemctl enable mutt-remediation.service

echo "Starting services..."
sudo systemctl start mutt-ingestor.service
sudo systemctl start mutt-alerter@{1..5}.service
sudo systemctl start mutt-moog-forwarder.service
sudo systemctl start mutt-webui.service
sudo systemctl start mutt-remediation.service

# 10. Check status
echo ""
echo "=== Service Status ==="
sudo systemctl status mutt-ingestor.service --no-pager
sudo systemctl status mutt-alerter@1.service --no-pager
sudo systemctl status mutt-webui.service --no-pager

echo ""
echo "=== Deployment Complete ==="
echo "Logs: journalctl -u mutt-* -f"
echo "Config: $MUTT_HOME/.env"
echo "Web UI: http://localhost:8090"
echo ""
echo "Next steps:"
echo "  1. Edit $MUTT_HOME/.env with production values"
echo "  2. Restart services: sudo systemctl restart mutt-*"
echo "  3. Check logs: sudo journalctl -u mutt-* -f"
