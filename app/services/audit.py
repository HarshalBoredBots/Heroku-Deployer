"""Fire-and-forget audit logging wrapper."""

import asyncio
import logging

from app.db.repositories import audit_logs

logger = logging.getLogger(__name__)


async def _write_safe(**kwargs) -> None:
    try:
        await audit_logs.write(**kwargs)
    except Exception:
        logger.exception("audit_write_failed")


def audit(actor: str, action: str, **kwargs) -> None:
    """Schedule an audit log write. Never raises."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_write_safe(actor=actor, action=action, **kwargs))
    except RuntimeError:
        pass
