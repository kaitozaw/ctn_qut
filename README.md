## Setup on EC2

Follow these steps to deploy and run the orchestrator on an EC2 instance.

### 0. Connect to EC2

From your local terminal, connect to the EC2 instance.

```bash
ssh -i ~/keys/ctn.pem ec2-user@<EC2_PUBLIC_IP>
```

### 1. Stop the running service

Stop the systemd service before replacing repository files.

```bash
sudo systemctl stop ctn-qut-orchestrator.service
```

### 2. Clone the repository

Switch to the legit user and refresh the repository.

```bash
sudo -iu legit
cd ~/apps
rm -rf ctn_qut
git clone https://github.com/kaitozaw/ctn_qut.git
cd ctn_qut
```

### 3. Copy configuration files

The runtime environment is located in ~/apps/legit-bots/.
Copy its configuration files into the ctn_qut directory.

```bash
cp ~/apps/legit-bots/.env ~/apps/ctn_qut/.env
cp ~/apps/legit-bots/config.json ~/apps/ctn_qut/config.json
```

### 4. Restart the service

Switch back (if needed) and restart the service:

```bash
exit   # if still in legit shell, go back to ec2-user
sudo systemctl start ctn-qut-orchestrator.service
```

### 5. Check service status and logs

After starting the service, you can verify its status and view logs.

- Check service status:

```bash
sudo systemctl status ctn-qut-orchestrator.service --no-pager
```

- Show the last 100 log lines:

```bash
sudo journalctl -u ctn-qut-orchestrator.service -n 100 --no-pager
```

- Show the full log history:

```bash
sudo journalctl -u ctn-qut-orchestrator.service
```

- Follow logs in real time:

```bash
sudo journalctl -u ctn-qut-orchestrator.service -f
```