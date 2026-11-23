# MetroScope — Production Operations Runbook

## 1. Daily Health & Monitoring Commands

MetroScope runs efficiently on an AWS EC2 `t3.small` instance without requiring heavy external monitoring agents (such as Prometheus, Datadog, or Grafana). Standard system utilities and Docker commands provide complete operational visibility.

### 1.1 Container Status & Health
```bash
# View container status, uptime, and health state
docker compose -f docker-compose.prod.yml ps

# Real-time resource utilization (CPU, Memory, Network I/O)
docker stats --no-stream
```

### 1.2 Memory Utilization Audit
Verify active memory usage against the **1,408 MB approved budget**:
```bash
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}"
```
Target thresholds:
- Host Free Memory: $> 350\text{ MB}$
- Swap Usage: $< 500\text{ MB}$

### 1.3 Service Logs Inspection
```bash
# Tail all logs
docker compose -f docker-compose.prod.yml logs -f --tail=100

# Tail specific services
docker compose -f docker-compose.prod.yml logs -f --tail=100 backend
docker compose -f docker-compose.prod.yml logs -f --tail=100 worker
docker compose -f docker-compose.prod.yml logs -f --tail=100 frontend
docker compose -f docker-compose.prod.yml logs -f --tail=100 nginx
docker compose -f docker-compose.prod.yml logs -f --tail=100 db
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
docker image prune -f

# Prune images older than 7 days (preserving active and current rollback images)
docker image prune -a --filter "until=168h" -f

# Prune dangling build cache
docker builder prune -f --filter "until=168h"
```

### 2.3 Log Rotation Enforcement
All containers are configured with `json-file` log limits (`max-size: 10m`, `max-file: 3`). If legacy docker logs are consuming space:
```bash
# Inspect container log sizes
sudo du -sh /var/lib/docker/containers/*/*-json.log
```

---

## 3. Let's Encrypt SSL/TLS Certificate Management

### 3.1 Initial Certificate Issuance via Certbot
Once DNS `A` records point `metroscope.news` and `www.metroscope.news` to the EC2 Elastic IP:

```bash
# Ensure Nginx is running and serving port 80
docker compose -f docker-compose.prod.yml up -d nginx

# Run Certbot in standalone container to obtain certificate
docker run -it --rm --name certbot \
  -v /opt/metroscope/infrastructure/nginx/certbot/conf:/etc/letsencrypt \
  -v /opt/metroscope/infrastructure/nginx/certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  --email contact@metroscope.news \
  --agree-tos --no-eff-email \
  -d metroscope.news -d www.metroscope.news

# Verify certificate files were created
ls -l /opt/metroscope/infrastructure/nginx/certbot/conf/live/metroscope.news/
# fullchain.pem, privkey.pem
```

### 3.2 Activate HTTPS in Nginx
Once certificates exist:
1. Open `/opt/metroscope/infrastructure/nginx/conf.d/metroscope.conf`.
2. Uncomment the `server { listen 443 ssl ... }` block.
3. Reload Nginx without downtime:
   ```bash
   docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
   ```

### 3.3 Automated Certificate Renewal via Cron
Add certificate renewal to `crontab -e`:
```bash
# Attempt renewal twice daily (at 03:00 and 15:00 UTC) and reload Nginx
0 3,15 * * * docker run --rm -v /opt/metroscope/infrastructure/nginx/certbot/conf:/etc/letsencrypt -v /opt/metroscope/infrastructure/nginx/certbot/www:/var/www/certbot certbot/certbot renew --webroot --webroot-path=/var/www/certbot --quiet && docker compose -f /opt/metroscope/docker-compose.prod.yml exec nginx nginx -s reload
```

---

## 4. Common Troubleshooting Scenarios

### Scenario A: Backend Reports Database Connection Error
```bash
# 1. Check if db container is running and healthy
docker compose -f docker-compose.prod.yml ps db

# 2. Inspect database logs
docker compose -f docker-compose.prod.yml logs --tail=50 db

# 3. Test database connectivity directly from host
docker compose -f docker-compose.prod.yml exec db pg_isready -U metroscope_user -d metroscope

# 4. If unhealthy, restart db cleanly
docker compose -f docker-compose.prod.yml restart db
```

### Scenario B: GDELT News Ingestion Delays or Rate Limits
- GDELT DOC 2.0 occasionally encounters temporary upstream latency.
- The worker uses exponential backoff (`tenacity`) with 3 retries and 15-minute polling.
- Check worker logs:
  ```bash
  docker compose -f docker-compose.prod.yml logs --tail=100 worker
  ```
- If GDELT blocks requests temporarily, the worker preserves existing records in PostgreSQL and resumes cleanly on the next cycle.

### Scenario C: High Host Memory Usage
If `free -m` indicates host available memory is $< 200\text{ MB}$:
```bash
# 1. Identify which container is consuming excess memory
docker stats --no-stream

# 2. If frontend or backend is near its limit, perform a rolling restart
docker compose -f docker-compose.prod.yml restart backend
docker compose -f docker-compose.prod.yml restart frontend

# 3. Drop Linux slab/dentry pagecache
sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
```

### Scenario D: Checking Newsletter Delivery & Subscriber State
```bash
# Query active subscriber count and recent delivery runs via API probe
curl -s http://localhost:8000/api/v1/newsletter/status | jq .
curl -s http://localhost:8000/health/metrics | jq .
```
