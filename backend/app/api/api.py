from fastapi import APIRouter
from app.api.endpoints import admin, admin_control_plane, shops, services, appointments, slots, webhook, ws, login, clients, public, tenants, telegram_bots, demo, ws_ticket, sla, features, _sentry_test

api_router = APIRouter()

api_router.include_router(login.router, tags=["login"])
api_router.include_router(admin_control_plane.router, tags=["admin", "control-plane"])
api_router.include_router(_sentry_test.router, tags=["_internal"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(telegram_bots.router, prefix="/tenants", tags=["telegram-bots"])
api_router.include_router(features.router, prefix="/features", tags=["features"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

api_router.include_router(shops.router, prefix="/shops", tags=["shops"])
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(slots.router, prefix="/slots", tags=["slots"])
api_router.include_router(sla.router, prefix="/sla", tags=["sla"])
api_router.include_router(webhook.router, tags=["telegram"])
api_router.include_router(ws.router, tags=["websocket"])
api_router.include_router(ws_ticket.router, tags=["websocket"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(sla.router, prefix="/sla", tags=["sla"])
api_router.include_router(demo.router)

# Slug-based public router: /{slug}/services/public, /{slug}/slots/public, etc.
slug_router = APIRouter(prefix="/{slug}")
slug_router.include_router(public.router, tags=["public"])
api_router.include_router(slug_router)

