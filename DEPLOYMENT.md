# Deployment Guide - Auto-Concierge v1.0

## Production Deployment with HTTPS

### Prerequisites
- Docker & Docker Compose installed
- Ports 80 and 443 open on your server
- Domain configured (using nip.io for automatic DNS)

### Current Configuration
- **Domain**: https://188-120-117-99.nip.io
- **IP Address**: 188.120.117.99
- **SSL**: Automatic Let's Encrypt certificates via Caddy

### Services
- **Frontend**: https://188-120-117-99.nip.io
- **API**: https://188-120-117-99.nip.io/api
- **API Docs**: https://188-120-117-99.nip.io/docs

### Deployment Steps

1. **Configure Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

2. **Deploy Services**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d --build
   ```

3. **Run Database Migrations**
   ```bash
   docker exec autoservice_api_prod alembic upgrade head
   ```

4. **Check Services Status**
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   ```

5. **View Logs**
   ```bash
   # All services
   docker-compose -f docker-compose.prod.yml logs -f
   
   # Specific service
   docker logs autoservice_caddy_prod -f
   ```

### SSL Certificate Notes
- Caddy automatically obtains and renews Let's Encrypt certificates
- Certificates are stored in `./infra_data/caddy_data/`
- First request may take a few seconds while certificate is obtained
- Ensure ports 80 and 443 are accessible from the internet

### Updating IP Address
If your IP changes, update:
1. `Caddyfile` - change domain to new IP
2. `.env` - update WEBAPP_URL
3. Restart services: `docker-compose -f docker-compose.prod.yml restart`

### Security Checklist
- ✅ HTTPS enabled with automatic certificates
- ✅ Security headers configured
- ✅ .env file excluded from git
- ✅ Database credentials secured
- ✅ API keys encrypted

### Troubleshooting

**SSL Certificate Issues**
```bash
# Check Caddy logs
docker logs autoservice_caddy_prod

# Verify domain resolves
nslookup 188-120-117-99.nip.io

# Test HTTPS
curl -I https://188-120-117-99.nip.io
```

**Port Conflicts**
```bash
# Check what's using ports 80/443
netstat -ano | findstr ":80"
netstat -ano | findstr ":443"
```

### Monitoring
- Access logs: `./infra_data/caddy_logs/access.log`
- Error logs: `docker logs <container_name>`
