from datetime import datetime, timedelta

from .models import Video
from .schemas import VideoStatus
from .services import get_fal_status


async def update_video():
    data = (
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
        except Exception:
            # Except convert to draft
            video.status = VideoStatus.draft
            await video.save()
