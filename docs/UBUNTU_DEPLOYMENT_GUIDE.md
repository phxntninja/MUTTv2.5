# MUTT v2.5 Ubuntu Deployment Guide

This guide provides detailed instructions for deploying the MUTT v2.5 application on an Ubuntu server. The primary deployment method uses `systemd` to manage the application services.

A deployment script, `deploy_ubuntu.sh`, is provided to automate these steps. You can run the script directly or follow the manual steps below for a more controlled installation.

## 1. Prerequisites

### 1.1. System Dependencies
-   An Ubuntu Server (20.04 LTS or newer is recommended).
-   `sudo` or root access.
-   Python v3.10.

To install Python 3.10 if it's not already present:
```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.10 python3.10-venv
```

### 1.2. External Services
The application requires the following external services to be running and accessible from the Ubuntu host:
-   **PostgreSQL:** For data storage.
-   **Redis:** For caching and message queuing.

The connection details for these services will be configured in the `.env` file.

## 2. Manual Deployment Steps

### 2.1. Create Application User and Group
Create a dedicated system user and group to run the application for better security and isolation.

```bash
sudo useradd --system --home-dir /opt/mutt --shell /bin/bash --create-home mutt
```

### 2.2. Create Directory Structure
Create the necessary directories for the application files, logs, and Python virtual environment.

```bash
sudo mkdir -p /opt/mutt/{services,scripts,database,logs,venv}
sudo chown -R mutt:mutt /opt/mutt
```

### 2.3. Install Application Code and Dependencies
As the `mutt` user, set up the Python virtual environment and install the required packages.

```bash
# Switch to the mutt user
sudo -iu mutt

# Create the virtual environment
python3.10 -m venv /opt/mutt/venv

# Activate the environment and install dependencies
source /opt/mutt/venv/bin/activate
pip install --upgrade pip
# Assuming you have the requirements.txt file in your current directory
pip install -r requirements.txt
# Deactivate when done
deactivate
```
*Note: You will need to copy the `requirements.txt` file to a location accessible by the `mutt` user or run the pip install command before switching users and then chown the venv.*

Now, copy the application files into the `/opt/mutt` directory.

```bash
sudo cp -r services/* /opt/mutt/services/
sudo cp -r scripts/* /opt/mutt/scripts/
sudo cp -r database/* /opt/mutt/database/
sudo chown -R mutt:mutt /opt/mutt
```

### 2.4. Configure Environment
Copy the environment template, set the ownership and permissions, and then edit it with your specific settings (e.g., database credentials, Redis host).

```bash
sudo cp .env.template /opt/mutt/.env
sudo chown mutt:mutt /opt/mutt/.env
sudo chmod 600 /opt/mutt/.env
```
**IMPORTANT:** You must edit this file with your production values.
```bash
sudo nano /opt/mutt/.env
```

### 2.5. Install Systemd Service Files
Copy the provided service files into the systemd directory.

```bash
sudo cp deployments/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### 2.6. Configure Firewall
If you are using `ufw`, allow access to the web UI port (8090/tcp).

```bash
sudo ufw allow 8090/tcp comment "MUTT Web UI"
sudo ufw enable
```

## 3. Managing Application Services

Once installed and configured, you can manage the MUTT services using `systemctl`.

### 3.1. Enable and Start Services
To have the services start on boot, enable them:
```bash
sudo systemctl enable mutt-ingestor.service
sudo systemctl enable mutt-alerter@{1..5}.service
sudo systemctl enable mutt-moog-forwarder.service
sudo systemctl enable mutt-webui.service
sudo systemctl enable mutt-remediation.service
```

To start the services immediately:
```bash
sudo systemctl start mutt-ingestor.service
sudo systemctl start mutt-alerter@{1..5}.service
sudo systemctl start mutt-moog-forwarder.service
sudo systemctl start mutt-webui.service
sudo systemctl start mutt-remediation.service
```

### 3.2. Check Service Status
To check the status of a service:
```bash
sudo systemctl status mutt-ingestor.service
sudo systemctl status mutt-alerter@1.service
```

### 3.3. View Logs
Logs are sent to the system journal. You can view them in real-time:
```bash
sudo journalctl -u mutt-* -f
```

To view logs for a specific service:
```bash
sudo journalctl -u mutt-webui.service -f
```

## 4. Systemd Service File Reference

For your reference, here are the contents of the `systemd` service files.

### `mutt-ingestor.service`
```ini
# File: deployments/systemd/mutt-ingestor.service
[Unit]
Description=MUTT Ingestor Service
After=network.target redis.service postgresql.service
Wants=redis.service postgresql.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
EnvironmentFile=/opt/mutt/.env
ExecStart=/opt/mutt/venv/bin/python -m services.ingestor_service
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mutt-ingestor

[Install]
WantedBy=multi-user.target
```

### `mutt-alerter@.service`
This is a template unit file, allowing multiple instances of the alerter service to run.
```ini
# File: deployments/systemd/mutt-alerter@.service
[Unit]
Description=MUTT Alerter Service (Instance %i)
After=network.target redis.service postgresql.service
Wants=redis.service postgresql.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
EnvironmentFile=/opt/mutt/.env
Environment="ALERTER_WORKER_ID=alerter-%i"
ExecStart=/opt/mutt/venv/bin/python -m services.alerter_service
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mutt-alerter-%i

[Install]
WantedBy=multi-user.target
```

### `mutt-moog-forwarder.service`
```ini
# File: deployments/systemd/mutt-moog-forwarder.service
[Unit]
Description=MUTT Moog Forwarder Service
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
EnvironmentFile=/opt/mutt/.env
ExecStart=/opt/mutt/venv/bin/python -m services.moog_forwarder_service
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mutt-moog-forwarder

[Install]
WantedBy=multi-user.target
```

### `mutt-remediation.service`
```ini
# File: deployments/systemd/mutt-remediation.service
[Unit]
Description=MUTT Remediation Service
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
EnvironmentFile=/opt/mutt/.env
ExecStart=/opt/mutt/venv/bin/python -m services.remediation_service
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mutt-remediation

[Install]
WantedBy=multi-user.target
```

### `mutt-webui.service`
```ini
# File: deployments/systemd/mutt-webui.service
[Unit]
Description=MUTT Web UI Service
After=network.target redis.service postgresql.service
Wants=redis.service postgresql.service

[Service]
Type=simple
User=mutt
Group=mutt
WorkingDirectory=/opt/mutt
EnvironmentFile=/opt/mutt/.env
ExecStart=/opt/mutt/venv/bin/gunicorn --workers 4 --bind 0.0.0.0:8090 --access-logfile - --error-logfile - --log-level info services.web_ui_service:app
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mutt-webui

[Install]
WantedBy=multi-user.target
```
