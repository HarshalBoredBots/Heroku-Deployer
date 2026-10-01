"""Entry point: run the Pyrogram bot + webhook server + health monitor."""

import asyncio
import logging
import os
import signal

import uvicorn

from app.bot.client import create_bot
from app.bot.handlers import register_all
from app.config import get_settings
from app.db.client import close_db, init_db
from app.db.repositories.accounts import ensure_default_account
from app.logging_config import setup_logging
from app.services.health_monitor import run_health_monitor, set_telegram_bot_for_monitor
from app.webhook.app import create_webhook_app

logger = logging.getLogger(__name__)


async def _startup_checks() -> None:
    """Verify DB connection, ensure default account exists."""
    await init_db()
    await ensure_default_account()


async def _run_all() -> None:
    await _startup_checks()

    settings = get_settings()
    bot = create_bot()
    register_all(bot)  # handlers registered via explicit imports; router last

    set_telegram_bot_for_monitor(bot)

    webhook_app = create_webhook_app()

    monitor_task = asyncio.create_task(run_health_monitor())

    # FIX #1 + #20: Read PORT from the environment (required by Heroku).
    # Heroku dynamically assigns a port via $PORT; hardcoding 8000 causes a
    # crash on startup because the assigned port is never bound.
    port = int(os.environ.get("PORT", 8000))
    config = uvicorn.Config(webhook_app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)

    try:
        await bot.start()
        logger.info("bot_started")
        await asyncio.gather(server.serve(), monitor_task)
    finally:
        logger.info("shutting_down")
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        try:
            await bot.stop()
        except Exception:
            pass
        server.should_exit = True
        await close_db()
        logger.info("shutdown_complete")


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _handle_sigterm(sig, frame):
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGTERM, _handle_sigterm)

    try:
        loop.run_until_complete(_run_all())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
