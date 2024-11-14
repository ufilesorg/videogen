import asyncio
import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apps.video.worker import update_video

from .config import Settings

irst_timezone = pytz.timezone("Asia/Tehran")
logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def worker():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_video, "interval", seconds=Settings.update_time)

    scheduler.start()

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()
