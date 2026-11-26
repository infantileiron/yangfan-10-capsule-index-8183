"""Redis wake-up helper shared by run and calibration producers."""

import logging

from redis.exceptions import RedisError

from src.config.settings import redis

WAKE_KEY = "workbench:wake"
logger = logging.getLogger(__name__)


def wake_worker(subject: str | None = None):
    if not subject:
        try:
            redis.lpush(WAKE_KEY, "wake")
        except RedisError:
            logger.warning("Redis wake signal failed; database polling remains available.")
        return
    try:
        with redis.pipeline() as commands:
            commands.lpush(WAKE_KEY, subject)
            commands.ltrim(WAKE_KEY, 0, 99)
            commands.execute()
    except RedisError:
        logger.warning("Redis wake signal failed for %s; database polling remains available.", subject)
