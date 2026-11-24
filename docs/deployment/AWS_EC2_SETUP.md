# MetroScope — AWS EC2 Setup & Host Hardening Guide

## 1. AWS Provisioning Specifications

- **AWS Region**: Sydney (`ap-southeast-2`)
- **Instance Type**: `t3.small` (2 vCPU, 2.0 GiB RAM)
- **AMI**: Ubuntu Server 24.04 LTS (Noble Numbat) — 64-bit (x86_64)
- **Storage**: 30 GB gp3 (General Purpose SSD, 3,000 IOPS, 125 MB/s throughput)
- **Elastic IP**: Allocated and attached to the instance
- **Host Timezone**: `Asia/Dhaka`

---

## 2. Security Group Configuration

Configure Security Group inbound rules with minimal attack surface:

| Type | Protocol | Port Range | Source | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | TCP | `22` | `<YOUR_RESTRICTED_IP>/32` | Administrative access |
| **HTTP** | TCP | `80` | `0.0.0.0/0`, `::/0` | Web traffic & Let's Encrypt ACME challenge |
| **HTTPS** | TCP | `443` | `0.0.0.0/0`, `::/0` | Secure web traffic |
| **Outbound** | All | All | `0.0.0.0/0` | Package updates, Webz.io API, GHCR |

> [!CAUTION]
> **Port 5432 (PostgreSQL) must NEVER be exposed publicly.** Port 8000 (Backend) and Port 3000 (Frontend) are also kept internal. Only ports 80 and 443 are published by Nginx.

---

## 3. Host Initialization & Directory Setup

Connect to the instance:
```bash
ssh -i ~/.ssh/metroscope_key.pem ubuntu@<EC2_ELASTIC_IP>
```

### 3.1 Host Directory Structure
Set up the production directory layout under `/srv/metroscope`:
```bash
sudo mkdir -p /srv/metroscope/{app,backups,config,data/media,data/photo-cards,data/postgres,secrets}
sudo chown -R ubuntu:ubuntu /srv/metroscope
sudo chmod 700 /srv/metroscope/secrets

# Prepare PostgreSQL storage for Alpine UID 70 (postgres user)
sudo chown -R 70:70 /srv/metroscope/data/postgres
sudo chmod 700 /srv/metroscope/data/postgres
```

### 3.2 Timezone Setup
```bash
sudo timedatectl set-timezone Asia/Dhaka
```

### 3.3 Configure Swap (Resource Protection on 2 GiB RAM)
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
echo 'vm.vfs_cache_pressure=50' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 3.4 Docker Engine & Compose Installation
Install Docker CE and Compose plugin via official Docker repositories:
```bash
sudo apt update && sudo apt install -y ca-certificates curl gnupg ufw fail2ban
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

> [!NOTE]
> The `ubuntu` user does not need to be in the `docker` group. All deployment scripts in `/srv/metroscope/app/scripts/` automatically detect whether `sudo` is required and execute `sudo docker` appropriately.

---

## 4. Docker JSON Log Rotation
To prevent container logs from filling the 30 GB disk, verify `/etc/docker/daemon.json`:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```
Reload docker:
```bash
sudo systemctl restart docker
```
