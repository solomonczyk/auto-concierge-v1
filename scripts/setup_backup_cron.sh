#!/bin/bash
# Remove any previously broken auto-concierge cron entries
crontab -l 2>/dev/null | grep -v 'Auto-Concierge\|autoservice_.*sql\|auto-concierge.*delete\|Daily dump\|Delete backups' > /tmp/crontab_clean.txt

# Append correct cron jobs (single-quoted heredoc prevents expansion here)
cat >> /tmp/crontab_clean.txt << 'CRONEOF'
# === Auto-Concierge PostgreSQL Backups ===
# Daily dump at 03:00 server time
0 3 * * * docker exec autoservice_db_prod pg_dump -U postgres autoservice | gzip > /var/backups/auto-concierge/autoservice_$(date +%F).sql.gz
# Delete backups older than 7 days at 03:30
30 3 * * * find /var/backups/auto-concierge -type f -name '*.sql.gz' -mtime +7 -delete
CRONEOF

crontab /tmp/crontab_clean.txt
echo "[OK] Crontab installed:"
crontab -l | tail -6
