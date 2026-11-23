# MetroScope — PostgreSQL Backup & Recovery Runbook

## 1. Backup Architecture Overview

MetroScope uses a practical, zero-dependency PostgreSQL backup and recovery system designed to run on the EC2 `t3.small` instance without exhausting host memory or storage.

### Key Characteristics:
- **Consistent Logical Dumps**: Generated via `pg_dump` with `--clean --if-exists --no-owner --no-privileges`.
- **Stream Compression**: Direct piped compression through `gzip -9` creates `.sql.gz` archives with ~85% space savings.
- **Integrity Validation**: Immediate test extraction via `gzip -t` confirms archive readability.
- **Checksum Verification**: Generates `.sha256` digest alongside every archive.
- **Configurable Retention**: Prunes local archives according to retention limits.
- **Optional S3 Offsite Sync**: Automatically pushes backups to an S3-compatible bucket if `BACKUP_S3_BUCKET` is defined.

---

## 2. Automated Daily Backups via Cron

Configure an automated daily backup job on the host via `crontab -e`:

```bash
# Open crontab for ubuntu user:
crontab -e

# Add automated daily backup at 02:30 AM UTC:
30 2 * * * /opt/metroscope/scripts/backup_postgres.sh >> /opt/metroscope/backups/cron.log 2>&1
```

### Retention Policy

| Tier | Window | Frequency | Pruning Schedule |
| :--- | :--- | :--- | :--- |
| **Daily** | Past 7 days | Every night (02:30 UTC) | Retained for 7 days (`RETENTION_DAILY_DAYS=7`) |
| **Weekly** | Past 4 weeks | Sunday night | Retained for 28 days (`RETENTION_WEEKLY_DAYS=28`) |
| **Monthly** | Past 3 months | 1st of month | Retained for 90 days (`RETENTION_MONTHLY_DAYS=90`) |

---

## 3. Manual Backup Execution

To generate a manual backup on demand (e.g. before applying migrations or upgrading images):

```bash
cd /opt/metroscope

# Run backup script
./scripts/backup_postgres.sh

# Verify output in backups directory
ls -lh backups/
# metroscope_pg_20261108_093000Z.sql.gz
# metroscope_pg_20261108_093000Z.sql.gz.sha256
```

---

## 4. Database Restoration Procedure

Restorations are executed via `scripts/restore_postgres.sh`. The script validates gzip integrity, checks the SHA-256 digest, requests user confirmation, streams the dump into `psql`, and executes post-restore verification queries.

### Step 1: List Available Backups
```bash
ls -lt /opt/metroscope/backups/*.sql.gz
```

### Step 2: Stop Ingestion Worker to Prevent Concurrent Writes
```bash
docker compose -f docker-compose.prod.yml stop worker
```

### Step 3: Execute Restoration
```bash
# Interactive mode (prompts for explicit 'yes' confirmation):
./scripts/restore_postgres.sh backups/metroscope_pg_20261108_093000Z.sql.gz

# Automated / non-interactive mode (for disaster recovery pipelines):
./scripts/restore_postgres.sh backups/metroscope_pg_20261108_093000Z.sql.gz --force
```

### Step 4: Review Post-Restore Diagnostics
The script automatically executes and displays verification counts:
```
--- Post-Restore Entity Counts ---
     entity      | count 
-----------------+-------
 news_articles   |  1842
 news_sources    |    24
 news_categories |     8
 email_subscribers|    47
 alembic_version |     1

Current Alembic database revision at: 0008_email_newsletter
```

### Step 5: Restart All Services
```bash
docker compose -f docker-compose.prod.yml start worker
docker compose -f docker-compose.prod.yml ps
```

---

## 5. Disaster Recovery: Restoring from Remote S3

If the local EC2 storage is lost or a new instance is provisioned:

```bash
# 1. Download latest archive from S3
aws s3 cp s3://<YOUR_BACKUP_BUCKET>/backups/metroscope_pg_latest.sql.gz /opt/metroscope/backups/
aws s3 cp s3://<YOUR_BACKUP_BUCKET>/backups/metroscope_pg_latest.sql.gz.sha256 /opt/metroscope/backups/

# 2. Execute restore
/opt/metroscope/scripts/restore_postgres.sh /opt/metroscope/backups/metroscope_pg_latest.sql.gz
```
