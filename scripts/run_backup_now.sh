#!/bin/bash
rm -f /var/backups/auto-concierge/autoservice_.sql.gz
FILENAME="/var/backups/auto-concierge/autoservice_$(date +%F).sql.gz"
docker exec autoservice_db_prod pg_dump -U postgres autoservice | gzip > "$FILENAME"
echo "Backup created: $FILENAME"
ls -lh /var/backups/auto-concierge/
