#　EC2 Deployment

## Prerequisites
- Before following these steps, make sure that:
    - You have the .pem private key file for the EC2 instance.
    - Your current IP address is allowed in the EC2 Security Group (port 22 for SSH).

## Initial Deploy on EC2

### 0. Connect to EC2
```bash
ssh -i ~/keys/ctn.pem ec2-user@<EC2_PUBLIC_IP>
```

### 1. Install base packages
```bash
sudo dnf -y update
sudo dnf -y install git python3 python3-pip
```

### 2. Create runtime user (no sudo, no password login)
```bash
sudo adduser legit
sudo passwd -l legit
sudo mkdir -p /home/legit/.ssh
sudo chown -R legit:legit /home/legit/.ssh
sudo chmod 700 /home/legit/.ssh
```

### 3. Setup app directory & venv
```bash
sudo -iu legit
mkdir -p ~/apps/legit-bots
cd ~/apps/legit-bots
python3 -m venv venv
~/apps/legit-bots/venv/bin/pip install --upgrade pip
```

### 4. Prepare configs & data
```bash
cd ~/apps/legit-bots
nano .env          # copy from local (change settings depending on which bots to run)
nano config.json   # copy from local (change *_db path to "/home/legit/apps/legit-bots/data/*_db")
mkdir -p data
```

### 5. Clone repository
```bash
cd ~/apps
git clone https://github.com/kaitozaw/ctn_qut.git
```

### 6. Install dependencies into venv
```bash
cd ~/apps/ctn_qut
source ~/apps/legit-bots/venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 7. Copy configuration files
```bash
cd ~/apps/ctn_qut
cp ~/apps/legit-bots/.env ~/apps/ctn_qut/.env
cp ~/apps/legit-bots/config.json ~/apps/ctn_qut/config.json
```

### 8. Setup systemd service
```bash
exit   # if still in legit shell, go back to ec2-user
```

```bash
sudo tee /etc/systemd/system/ctn-qut-orchestrator.service >/dev/null <<'UNIT'
[Unit]
Description=CtN QUT Orchestrator (Twooter bot)
After=network-online.target
Wants=network-online.target

[Service]
User=legit
Group=legit
WorkingDirectory=/home/legit/apps/ctn_qut
EnvironmentFile=/home/legit/apps/ctn_qut/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/legit/apps/legit-bots/venv/bin/python -m orchestrators.orchestrator

Restart=on-failure
RestartSec=3
KillSignal=SIGINT
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
UNIT
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable ctn-qut-orchestrator
sudo systemctl start ctn-qut-orchestrator
sudo systemctl status ctn-qut-orchestrator.service --no-pager
sudo journalctl -u ctn-qut-orchestrator.service -f
```

## Redeploy on EC2

### 0. Connect to EC2
```bash
ssh -i ~/keys/ctn.pem ec2-user@<EC2_PUBLIC_IP>
```

### 1. Stop the running service
```bash
sudo systemctl stop ctn-qut-orchestrator.service
```

### 2. Clone the repository
```bash
sudo -iu legit
cd ~/apps
rm -rf ctn_qut
git clone https://github.com/kaitozaw/ctn_qut.git
```

### 3. Copy configuration files
```bash
cd ~/apps/ctn_qut
cp ~/apps/legit-bots/.env ~/apps/ctn_qut/.env
cp ~/apps/legit-bots/config.json ~/apps/ctn_qut/config.json
```

### 4. Restart the service
```bash
exit   # if still in legit shell, go back to ec2-user
sudo systemctl start ctn-qut-orchestrator.service
```

### 5. Check service status and logs
```bash
sudo systemctl status ctn-qut-orchestrator.service --no-pager
sudo journalctl -u ctn-qut-orchestrator.service -f
```