from fastapi import APIRouter
from app.api.endpoints import shops, services, appointments, slots, webhook, ws, login, clients, public, tenants, demo, ws_ticket

api_router = APIRouter()

api_router.include_router(login.router, tags=["login"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])

api_router.include_router(shops.router, prefix="/shops", tags=["shops"])
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(slots.router, prefix="/slots", tags=["slots"])
api_router.include_router(webhook.router, tags=["telegram"])
api_router.include_router(ws.router, tags=["websocket"])
api_router.include_router(ws_ticket.router, tags=["websocket"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(demo.router)

# Slug-based public router: /{slug}/services/public, /{slug}/slots/public, etc.
slug_router = APIRouter(prefix="/{slug}")
slug_router.include_router(public.router, tags=["public"])
api_router.include_router(slug_router)

