# MetroScope — Production Operations Runbook

## 1. Daily Health & Monitoring Commands

MetroScope runs efficiently on an AWS EC2 `t3.small` instance in Sydney (`ap-southeast-2`) without requiring heavy external monitoring agents. Standard system utilities and Docker commands provide complete operational visibility.

### 1.1 Container Status & Health
```bash
cd /srv/metroscope/app

# View container status, uptime, and health state
sudo docker compose -f docker-compose.prod.yml ps

# Real-time resource utilization (CPU, Memory, Network I/O)
sudo docker stats --no-stream
```

### 1.2 Memory Utilization Audit
Verify active memory usage against the **1,408 MB approved budget**:
```bash
sudo docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}"
```
Target thresholds:
- Host Free Memory: $> 350\text{ MB}$
- Swap Usage: $< 500\text{ MB}$

### 1.3 Service Logs Inspection
```bash
cd /srv/metroscope/app

# Tail all logs
sudo docker compose -f docker-compose.prod.yml logs -f --tail=100

# Tail specific services
sudo docker compose -f docker-compose.prod.yml logs -f --tail=100 backend
sudo docker compose -f docker-compose.prod.yml logs -f --tail=100 frontend
sudo docker compose -f docker-compose.prod.yml logs -f --tail=100 nginx
sudo docker compose -f docker-compose.prod.yml logs -f --tail=100 db
```

---

## 2. Disk & Resource Management (30 GB gp3 Storage)

The host operates on a 30 GB EBS volume. Follow these hygiene practices to prevent disk exhaustion:

### 2.1 Check Disk Space
```bash
df -h /
```
- **Normal**: $< 70\%$ utilization.
- **Warning**: $> 80\%$ utilization.
- **Critical**: $> 90\%$ utilization.

### 2.2 Safe Docker Image & Build Cache Cleanup
Never delete running containers, active images, or persistent database volumes:
```bash
# Prune dangling/untagged images
sudo docker image prune -f

# Prune images older than 7 days (preserving active and current rollback images)
sudo docker image prune -a --filter "until=168h" -f

# Prune dangling build cache
sudo docker builder prune -f --filter "until=168h"
```

---

## 3. Let's Encrypt SSL/TLS Certificate Management

### 3.1 Initial Certificate Issuance & Activation (Stage B)
Once DNS `A` records point `themetroscope.com`, `www.themetroscope.com`, and `api.themetroscope.com` to the EC2 Elastic IP:

```bash
cd /srv/metroscope/app
./scripts/enable_ssl.sh admin@themetroscope.com
```

### 3.2 Automated Certificate Renewal via Cron
Add certificate renewal to `crontab -e`:
```bash
# Attempt renewal twice daily (at 03:00 and 15:00 UTC) and reload Nginx
0 3,15 * * * sudo docker compose -f /srv/metroscope/app/docker-compose.prod.yml --profile certbot run --rm certbot renew --webroot --webroot-path=/var/www/certbot --quiet && sudo docker compose -f /srv/metroscope/app/docker-compose.prod.yml exec nginx nginx -s reload
```

---

## 4. Common Troubleshooting Scenarios

### Scenario A: Backend Reports Database Connection Error
```bash
# 1. Check if db container is running and healthy
sudo docker compose -f docker-compose.prod.yml ps db

# 2. Inspect database logs
sudo docker compose -f docker-compose.prod.yml logs --tail=50 db

# 3. Test database connectivity directly from container
sudo docker compose -f docker-compose.prod.yml exec db pg_isready -U metroscope_user -d metroscope

# 4. If unhealthy, restart db cleanly
sudo docker compose -f docker-compose.prod.yml restart db
```

### Scenario B: High Host Memory Usage
If `free -m` indicates host available memory is $< 200\text{ MB}$:
```bash
# 1. Identify which container is consuming excess memory
sudo docker stats --no-stream

# 2. If frontend or backend is near its limit, perform a rolling restart
sudo docker compose -f docker-compose.prod.yml restart backend
sudo docker compose -f docker-compose.prod.yml restart frontend

# 3. Drop Linux slab/dentry pagecache
sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
```

### Scenario C: Starting the Worker Service (When Authorized by Operator)
When the operator explicitly authorizes background operations (Webz.io collection, social publishing):
```bash
# Start the worker with its explicit Compose profile:
sudo docker compose -f docker-compose.prod.yml --profile worker up -d worker

# Verify worker startup logs:
sudo docker compose -f docker-compose.prod.yml logs -f --tail=50 worker
```
