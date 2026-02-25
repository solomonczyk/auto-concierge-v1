
API Request
06:06 PM
$0.0649

Kilo said
Проверю текущую конфигурацию nginx для nikasal.fvds.ru — возможно там уже есть /concierge/:


Checkpoint

Running

ssh root@109.172.114.149 "cat /etc/nginx/sites-available/autoservice"
server {
    listen 80;
    server_name nikasal.fvds.ru;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/v1/ws {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

Auto-approved commands

API Request
06:06 PM
$0.0624

Kilo said
Нет /concierge/ пути. Проверю