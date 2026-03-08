"""
Shared slowapi rate limiter instance.
Import this in main.py and any endpoint module that needs rate limiting.
Using a single instance ensures all limits share the same in-memory store.
"""
from fastapi import Request
from slowapi import Limiter

LOGIN_RATE_LIMIT = "10/minute"
PUBLIC_BOOKING_RATE_LIMIT = "5/minute"


def get_client_ip(request: Request) -> str:
    """Prefer proxy-forwarded client IP, fallback to direct socket address."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip

    client = request.client
    if client and client.host:
        return client.host

    return "unknown"


limiter = Limiter(key_func=get_client_ip)
