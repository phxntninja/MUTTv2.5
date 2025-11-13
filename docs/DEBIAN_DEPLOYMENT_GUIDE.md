# MUTT v2.5 Debian Deployment Guide

This guide provides detailed instructions for deploying the MUTT v2.5 application on a Debian server. The primary deployment method uses `systemd` to manage the application services.

A deployment script, `deploy_debian.sh`, is provided to automate these steps. You can run the script directly or follow the manual steps below for a more controlled installation.

## 0. A Note on `sudo`
Minimal Debian installations may not include the `sudo` package. If the `sudo` command is not found, you can either run the commands as the `root` user or install it:
```bash
# Become root
su -
# Install sudo
apt update
apt install sudo
# Add your user to the sudo group (replace 'your_user' with your username)
usermod -aG sudo your_user
# Log out and log back in for the group change to take effect
exit
```

## 1. Prerequisites

### 1.1. System Dependencies
-   A Debian Server (Debian 11 "Bullseye" or newer is recommended).
-   `sudo` or root access.
-   Python v3.10.

To install Python 3.10 if it's not already present, you may need to add a third-party repository, as it may not be in the default Debian repositories. The "deadsnakes" PPA is a common choice for both Ubuntu and Debian.

```bash
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.10 python3.10-venv
```

### 1.2. External Services
The application requires the following external services to be running and accessible from the Debian host:
-   **PostgreSQL:** For data storage.
-   **Redis:** For caching and message queuing.

The connection details for these services will be configured in the `.env` file.

## 2. Manual Deployment Steps

### 2.1. Create Application User and Group
Create a dedicated system user and group to run the application.

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
Copy the environment template, set the ownership and permissions, and then edit it with your specific settings.

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
If you are using `ufw` (Uncomplicated Firewall), allow access to the web UI port (8090/tcp).

```bash
sudo ufw allow 8090/tcp comment "MUTT Web UI"
sudo ufw enable
```
If `ufw` is not installed, you can install it with `sudo apt install ufw`.

## 3. Managing Application Services

You can manage the MUTT services using `systemctl`.

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
```bash
sudo systemctl status mutt-ingestor.service
```

### 3.3. View Logs
```bash
sudo journalctl -u mutt-* -f
```

## 4. Systemd Service File Reference
The `systemd` service files used for Debian are identical to those used for other Linux distributions. They can be found in the `deployments/systemd/` directory.
