import logging
from datetime import datetime, timedelta

from utils import finance

from .models import Video
from .schemas import VideoStatus
from .services import get_fal_status


async def update_video():
    data: list[Video] = (
        await Video.get_query()
        .find(
            {
                "request_id": {"$ne": None},
                "created_at": {"$lte": datetime.now() - timedelta(minutes=3)},
                "status": {"$nin": VideoStatus.done_statuses()},
            }
        )
        .to_list()
    )

    for video in data:
        try:
            await get_fal_status(video)
        except Exception as e:
            # Except convert to draft
            logging.error(f"update video failed {type(e)} {e}")
            video.status = VideoStatus.error
            await video.save_report(f"update video failed {type(e)} {e}")
            await finance.cancel_usage(video)
