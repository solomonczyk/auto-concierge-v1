SERVICE_HEALTH_PROFILES: dict[str, list[str]] = {
    "api": ["db", "redis"],
    "worker_rq": ["redis"],
    "scheduler": ["db"],
    "bot": ["db", "telegram_init"],
}

