from singleton import Singleton
from datetime import datetime, timedelta
from .models import Video
from .schemas import VideoStatus
from .services import get_fal_status

async def update_video():
    done_statuses = [
        VideoStatus.done,
        VideoStatus.completed,
        VideoStatus.ok,
        VideoStatus.cancelled,
        VideoStatus.error,
    ]
    data = await Video.get_query().find(
        {
            "request_id": {"$ne": None},
            "created_at": {"$lte": datetime.utcnow() - timedelta(minutes=3)},
            "status": {"$nin": done_statuses}
        }
    ).to_list()
    
    for video in data:
        try:
            await get_fal_status(video)
        except Exception as e:
            # Except convert to draft
            video.status = VideoStatus.draft
            await video.save()
