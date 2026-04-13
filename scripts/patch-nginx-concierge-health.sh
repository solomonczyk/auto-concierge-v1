#!/bin/bash
set -eu
CFG=/etc/nginx/sites-available/bt-aistudio
cp -a "$CFG" "${CFG}.bak.concierge-health.$(date +%s)"
if grep -q 'location = /concierge/api/health' "$CFG"; then
  echo "already patched"
  exit 0
fi
python3 << 'PY'
from pathlib import Path
p = Path("/etc/nginx/sites-available/bt-aistudio")
text = p.read_text()
old = """    location = /concierge/live {
        proxy_pass http://127.0.0.1:8000/live;
        proxy_set_header Host $host;
    }
}"""
new = """    location = /concierge/live {
        proxy_pass http://127.0.0.1:8000/live;
        proxy_set_header Host $host;
    }

    # Backend health (FastAPI: /health, not /api/health)
    location = /concierge/health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /concierge/api/health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}"""
if old not in text:
    raise SystemExit("pattern not found")
p.write_text(text.replace(old, new, 1))
print("nginx config updated")
PY
nginx -t
nginx -s reload || service nginx reload || true
echo done
