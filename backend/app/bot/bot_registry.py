"""
Bot registry for multi-bot runtime.

Provides lazy Bot instance creation and in-memory caching:
token -> Bot
"""
import logging
from aiogram import Bot

logger = logging.getLogger(__name__)


class BotRegistry:
    def __init__(self) -> None:
        self._bots: dict[str, Bot] = {}

    def get_bot(self, token: str) -> Bot:
        if not token or not token.strip():
            raise ValueError("Telegram bot token is required")

        token = token.strip()

        existing = self._bots.get(token)
        if existing is not None:
            return existing

        bot = Bot(token=token)
        self._bots[token] = bot
        logger.info("Telegram bot instance registered in BotRegistry")
        return bot

    def has_bot(self, token: str) -> bool:
        return token.strip() in self._bots if token else False

    def remove_bot(self, token: str) -> bool:
        if not token:
            return False
        return self._bots.pop(token.strip(), None) is not None

    def count(self) -> int:
        return len(self._bots)


bot_registry = BotRegistry()
