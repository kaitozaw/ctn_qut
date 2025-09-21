## Setup on EC2

Follow these steps to deploy and run the orchestrator on an EC2 instance.

### 0. Connect to EC2

From your local terminal, connect to the EC2 instance.

```bash
ssh -i ~/keys/ctn.pem ec2-user@<EC2_PUBLIC_IP>
sudo -iu legit
```

### 1. Clone the repository

If an old `ctn_qut` directory already exists, remove it first to avoid conflicts.  
Then clone the latest version from GitHub.

```bash
cd ~/apps
rm -rf ctn_qut        # remove existing directory if present
git clone https://github.com/kaitozaw/ctn_qut.git
cd ctn_qut
```

### 2. Copy configuration files

The runtime environment is located in ~/apps/legit-bots/.
Copy its configuration files into the ctn_qut directory.

```bash
cp ~/apps/legit-bots/config.json ~/apps/ctn_qut/config.json
cp ~/apps/legit-bots/.env ~/apps/ctn_qut/.env
```