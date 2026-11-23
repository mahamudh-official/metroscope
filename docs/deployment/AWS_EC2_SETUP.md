# MetroScope — AWS EC2 Setup & Host Hardening Guide

## 1. AWS Provisioning Specifications

- **AWS Region**: Mumbai (`ap-south-1`)
- **Instance Type**: `t3.small` (2 vCPU, 2.0 GiB RAM)
- **AMI**: Ubuntu Server 24.04 LTS (Noble Numbat) — 64-bit (x86_64)
- **Storage**: 30 GB gp3 (General Purpose SSD, 3,000 IOPS, 125 MB/s throughput)
- **Elastic IP**: Required (allocates permanent static public IPv4)

---

## 2. Security Group Configuration

Create an EC2 Security Group (e.g., `metroscope-production-sg`) with minimal inbound attack surface:

| Type | Protocol | Port Range | Source | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | TCP | `22` | `<YOUR_ADMIN_IP>/32` | Administrative access (Restrict to trusted IP) |
| **HTTP** | TCP | `80` | `0.0.0.0/0`, `::/0` | Web traffic & ACME challenge |
| **HTTPS** | TCP | `443` | `0.0.0.0/0`, `::/0` | Secure web traffic |
| **Outbound** | All | All | `0.0.0.0/0` | GDELT API, package updates, git, GHCR |

> [!CAUTION]
> **Port 5432 (PostgreSQL) must NEVER be exposed publicly.** All database communication occurs strictly across the internal Docker bridge network (`metroscope_prod_net`).

---

## 3. Host Initialization & Base Hardening

Connect to the newly provisioned instance:

```bash
ssh -i ~/.ssh/metroscope_key.pem ubuntu@<EC2_ELASTIC_IP>
```

### 3.1 Update System Packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git unzip htop ufw fail2ban unattended-upgrades
```

### 3.2 Configure Swap Space (Resource Stability on 2GB RAM)
To protect against burst kernel Out-Of-Memory (OOM) killer events on a 2GB RAM instance:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Persist swap across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Tune swappiness for server workloads
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
echo 'vm.vfs_cache_pressure=50' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 3.3 Install Official Docker Engine & Docker Compose
```bash
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Grant ubuntu user access to docker without sudo
sudo usermod -aG docker ubuntu
```

### 3.4 Configure Host Firewall (UFW)
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'
sudo ufw enable
```

### 3.5 Configure SSH Hardening
Edit `/etc/ssh/sshd_config.d/50-cloud-init.conf` or `/etc/ssh/sshd_config`:
```bash
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

### 3.6 Enable Automated Security Updates
```bash
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

---

## 4. MetroScope Application Setup on Host

```bash
# Create application root directory
sudo mkdir -p /opt/metroscope
sudo chown -R ubuntu:ubuntu /opt/metroscope
cd /opt/metroscope

# Clone the repository
git clone https://github.com/<your-org>/metroscope.git .

# Create and lock down the production environment file
cp .env.production.template .env
chmod 600 .env

# Edit .env and supply strong randomly generated passwords
# For POSTGRES_PASSWORD, generate with: openssl rand -hex 24
nano .env

# Create Certbot directories for Let's Encrypt
mkdir -p infrastructure/nginx/certbot/conf infrastructure/nginx/certbot/www
```
