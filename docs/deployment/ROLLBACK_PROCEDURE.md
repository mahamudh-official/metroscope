# MetroScope — Production Rollback Procedure

## 1. Overview & Strategy

MetroScope employs an **immutable image rollback strategy**. Every release deployed on production is tagged with its git commit SHA (`${IMAGE_TAG}`) and recorded in `/srv/metroscope/app/.last_deployed_version`.

### Strict Guardrails:
- **No Automatic Migration Downgrades**: Database migrations are **never automatically downgraded** during an application container rollback. Reversing migrations can delete production columns or tables.
- **Zero-Volume Destruction**: The command `docker compose down -v` is strictly prohibited in all scripts and manual procedures.
- **Safe State Preservation**: Rollback restores `backend`, `frontend`, and `nginx` to the previously validated image tags. The background worker remains stopped.

---

## 2. Automated Rollback

If health checks fail during automated deployment (probes fail on `backend`, `frontend`, or `nginx`), `scripts/deploy.sh` automatically invokes `scripts/rollback.sh` using the previously deployed image tag:

```bash
# Automated trigger inside deploy.sh:
./scripts/rollback.sh "${PREVIOUS_IMAGE_TAG}"
```

---

## 3. Manual Rollback Procedure

If an issue is detected in production after a successful deployment:

### Option A: Rollback to the Immediately Preceding Release
```bash
ssh -i ~/.ssh/metroscope_key.pem ubuntu@<EC2_IP>

cd /srv/metroscope/app

# Execute rollback using recorded version history:
./scripts/rollback.sh
```

### Option B: Rollback to a Specific Historical Tag
```bash
# Example: rollback to specific known-good release commit SHA
./scripts/rollback.sh <PREVIOUS_COMMIT_SHA>
```
