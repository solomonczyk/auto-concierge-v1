#!/bin/bash
# ================================================================
# Настройка /concierge/ маршрута на bt-aistudio.ru
# Запускать на сервере: bash /root/auto-concierge-v1/setup-nginx-concierge.sh
# ================================================================

set -e

# ── Найти nginx конфиг bt-aistudio.ru ──────────────────────────
TARGET_CONF=""
for f in /etc/nginx/sites-available/bt-aistudio.ru \
          /etc/nginx/sites-available/autoservice \
          /etc/nginx/conf.d/bt-aistudio.ru.conf; do
    if [ -f "$f" ]; then
        TARGET_CONF="$f"
        break
    fi
done

if [ -z "$TARGET_CONF" ]; then
    TARGET_CONF=$(grep -rl "bt-aistudio" /etc/nginx/ 2>/dev/null | head -1)
fi

if [ -z "$TARGET_CONF" ]; then
    echo "❌ Конфиг nginx для bt-aistudio.ru не найден!"
    echo "   Доступные конфиги:"
    ls /etc/nginx/sites-available/ 2>/dev/null
    ls /etc/nginx/conf.d/ 2>/dev/null
    exit 1
fi

echo "📁 Конфиг: $TARGET_CONF"
cp "$TARGET_CONF" "${TARGET_CONF}.bak.$(date +%Y%m%d_%H%M%S)"
echo "✅ Бэкап создан"

# ── Проверить — блок уже есть? ──────────────────────────────────
if grep -q "location /concierge/" "$TARGET_CONF"; then
    echo "⚠️  /concierge/ уже настроен. Пропускаем добавление."
else
    # Вставить блок перед последней } в файле
    CONCIERGE_BLOCK='
    # Auto-Concierge v1
    location /concierge/ {
        proxy_pass http://127.0.0.1:8081/concierge/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API авто-консьержа (если фронтенд проксирует /api/ через основной nginx)
    location /api/v1/ {
        proxy_pass http://127.0.0.1:8002/api/v1/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket авто-консьержа
    location /api/v1/ws {
        proxy_pass http://127.0.0.1:8002/api/v1/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
'
    # Берём всё кроме последней строки '}', вставляем блок, добавляем '}'
    head -n -1 "$TARGET_CONF" > /tmp/nginx_new.conf
    echo "$CONCIERGE_BLOCK" >> /tmp/nginx_new.conf
    echo "}" >> /tmp/nginx_new.conf
    cp /tmp/nginx_new.conf "$TARGET_CONF"
    echo "✅ Блок /concierge/ добавлен"
fi

# ── Проверка и перезагрузка ────────────────────────────────────
echo ""
echo "🔍 Проверяем синтаксис nginx..."
nginx -t

echo "🔄 Перезагружаем nginx..."
systemctl reload nginx

echo ""
echo "════════════════════════════════════════════════"
echo "✅ nginx настроен!"
echo ""
echo "📦 Теперь пересобери frontend-контейнер:"
echo "   cd /root/auto-concierge-v1"
echo "   docker-compose -f docker-compose.prod.yml up -d --build frontend"
echo ""
echo "🌐 Затем открой: https://bt-aistudio.ru/concierge/"
echo "════════════════════════════════════════════════"
