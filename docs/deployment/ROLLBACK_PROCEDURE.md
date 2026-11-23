# MetroScope — Production Rollback Procedure

## 1. Overview & Strategy

MetroScope employs an **immutable image rollback strategy**. Every release deployed on production is tagged with its git commit SHA (`${{ github.sha }}`) and recorded in `/opt/metroscope/.last_deployed_version`.

### Strict Guardrails:
- **No Automatic Migration Downgrades**: Database migrations are **never automatically downgraded** during an application container rollback. Reversing migrations can delete production columns or tables.
- **Backward-Compatible Schema Design**: All database migrations must follow expand/contract patterns so earlier application images remain compatible with newer schemas.
- **Zero-Volume Destruction**: The command `docker compose down -v` is strictly prohibited in all scripts and manual procedures.

---

## 2. Automated Rollback

If health checks fail during automated deployment (HTTP 200 probe fails on `/health/ready` or `/`), `scripts/deploy.sh` automatically invokes `scripts/rollback.sh` using the previously deployed image tag:

```bash
# Automated trigger inside deploy.sh:
./scripts/rollback.sh "${PREVIOUS_IMAGE_TAG}"
```

---

## 3. Manual Rollback Procedure

If an issue is detected in production after a successful deployment (e.g. an unexpected runtime bug or upstream integration anomaly):

### Option A: Rollback to the Immediately Preceding Release
```bash
# SSH into EC2 instance
ssh -i ~/.ssh/metroscope_key.pem ubuntu@<EC2_IP>

cd /opt/metroscope

# Execute rollback using recorded version history
./scripts/rollback.sh
```

### Option B: Rollback to a Specific Historical Tag
```bash
# Example: rollback to specific known-good release commit SHA
./scripts/rollback.sh 8b73f910486c085ab924cf05c93da4c1ea55bf51
```

---

## 4. Migration Downgrade Guidelines (If Schema Reversal is Explicitly Required)

If and only if an engineering review determines that a migration itself must be rolled back:

1. **Take an Immediate Backup**:
   ```bash
   ./scripts/backup_postgres.sh
   ```

2. **Check Current Migration Revision**:
   ```bash
   docker compose -f docker-compose.prod.yml run --rm backend alembic current
   ```

3. **Downgrade Migration Carefully**:
   ```bash
   # Revert exactly one migration revision
   docker compose -f docker-compose.prod.yml run --rm backend alembic downgrade -1
   ```

4. **Verify Revision Status**:
   ```bash
   docker compose -f docker-compose.prod.yml run --rm backend alembic current
   ```

---

## 5. Post-Rollback Health Verification

```bash
# Run comprehensive diagnostic validation script
./scripts/validate_deployment.sh

# Verify backend health probes
curl -I http://localhost:8000/health/ready
curl -s http://localhost:8000/health/metrics | jq .

# Verify frontend responses
curl -I http://localhost:3000/
```
