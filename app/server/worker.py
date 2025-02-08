import asyncio
import logging

# import pytz
from apps.video.worker import update_video
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import Settings

# irst_timezone = pytz.timezone("Asia/Tehran")
logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def worker():
    await update_video()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_video, "interval", seconds=Settings.update_time)

    scheduler.start()

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()
