# MetroScope — PostgreSQL Backup & Disaster Recovery Runbook

## 1. Backup Architecture Overview

MetroScope employs an automated logical backup and tiered retention system designed for operational reliability on AWS EC2 `t3.small` and full portability across cloud and VPS providers (such as Hostinger VPS).

### Key Characteristics:
- **Clean Logical Dumps**: Generated via `pg_dump` with `--clean --if-exists --no-owner --no-privileges`.
- **Stream Compression**: Piped through `gzip -9` creating `.sql.gz` archives.
- **Integrity Verification**: Archive readability validated immediately via `gzip -t`.
- **Cryptographic Checksums**: Generates `.sha256` digest alongside every archive.
- **Tiered Retention Policy**: Enforces 7 Daily, 4 Weekly, and 3 Monthly retention tiers.
- **Zero-Secret Leakage**: Database passwords are provided via environment variables, never logged.
- **Portability Manifest**: Exports metadata (`latest_backup_manifest.json`) for seamless migration.

---

## 2. Retention Policy Architecture

Backups are organized in `/srv/metroscope/backups/`:

```text
/srv/metroscope/backups/
├── daily/                        # Retained for 7 days (pruned via mtime +7)
│   ├── metroscope_pg_20261124_023000Z.sql.gz
│   └── metroscope_pg_20261124_023000Z.sql.gz.sha256
├── weekly/                       # Promoted every Sunday; retained for 28 days
│   └── metroscope_pg_20261122_023000Z.sql.gz
├── monthly/                      # Promoted on the 1st of every month; retained for 90 days
│   └── metroscope_pg_20261101_023000Z.sql.gz
├── backup.log                    # Append-only execution log
└── latest_backup_manifest.json   # Machine-readable portability manifest
```

| Tier | Trigger | Retention Window | Max Retained |
|---|---|---|---|
| **Daily** | Nightly at 02:30 UTC | 7 Days | 7 backups |
| **Weekly** | Every Sunday | 28 Days (4 Weeks) | 4 backups |
| **Monthly** | 1st of each Month | 90 Days (3 Months) | 3 backups |

---

## 3. Automated Nightly Cron Setup

Install the backup job under the `ubuntu` user crontab:

```bash
crontab -e

# Run nightly at 02:30 UTC:
30 2 * * * /srv/metroscope/app/scripts/backup_postgres.sh >> /srv/metroscope/backups/cron.log 2>&1
```

---

## 4. Manual Backup Execution

To create an on-demand backup prior to applying migrations, updates, or maintenance:

```bash
cd /srv/metroscope/app
./scripts/backup_postgres.sh
```

---

## 5. Database Restoration Procedure

Restorations are executed via `scripts/restore_postgres.sh`. The script validates gzip integrity, checks the SHA-256 digest, requests user confirmation, streams the dump into `psql`, and verifies entity row counts.

### Step 1: List Available Backups
```bash
ls -lt /srv/metroscope/backups/daily/*.sql.gz
```

### Step 2: Execute Restore
```bash
# Interactive mode (prompts for confirmation):
./scripts/restore_postgres.sh /srv/metroscope/backups/daily/metroscope_pg_20261124_023000Z.sql.gz

# Automated / non-interactive mode:
./scripts/restore_postgres.sh /srv/metroscope/backups/daily/metroscope_pg_20261124_023000Z.sql.gz --force
```

### Step 3: Verify Integrity
The script automatically queries entity counts for `news_articles`, `news_sources`, `news_categories`, `social_posts`, and `alembic_version`.

---

## 6. Migration to Another VPS (e.g. Hostinger VPS)

To migrate MetroScope to another server:

1. **On Source Server (AWS EC2):**
   ```bash
   cd /srv/metroscope/app
   ./scripts/backup_postgres.sh
   tar -czf /tmp/metroscope_migration.tar.gz \
       /srv/metroscope/backups/daily/latest* \
       /srv/metroscope/app/.env \
       /srv/metroscope/app/docker-compose.prod.yml
   ```
2. **Transfer to Destination Server:**
   ```bash
   scp /tmp/metroscope_migration.tar.gz user@<DESTINATION_IP>:/tmp/
   ```
3. **On Destination Server (Hostinger):**
   - Install Docker and Docker Compose.
   - Clone `mahamudh-official/metroscope` into `/srv/metroscope/app`.
   - Prepare `/srv/metroscope/data/postgres` (`chown -R 70:70`, `chmod 700`).
   - Extract `.env` into `/srv/metroscope/app/.env`.
   - Start database: `sudo docker compose -f docker-compose.prod.yml up -d db`.
   - Restore database: `./scripts/restore_postgres.sh <transferred_backup_file>.sql.gz --force`.
   - Deploy stack: `./scripts/deploy.sh`.

---

## 7. RPO and RTO Specifications

- **Recovery Point Objective (RPO)**: Up to 24 hours with daily backups. A logical backup captures state at execution time. It is not continuous replication.
- **Recovery Time Objective (RTO)**: Under 5 minutes to restore the database dump and restart application containers.
