import logging

from fastapi_mongo_base.utils import basic

from .models import Video
from .schemas import VideoStatus
from .services import get_update


@basic.try_except_wrapper
async def update_video():
    data: list[Video] = (
        await Video.get_query()
        .find(
            {
                "request_id": {"$ne": None},
                # "created_at": {"$lte": datetime.now() - timedelta(minutes=3)},
                "status": {"$nin": VideoStatus.done_statuses()},
            }
        )
        .to_list()
    )

    for video in data:
        try:
            await get_update(video)
        except Exception as e:
            import traceback

            traceback_str = "".join(traceback.format_tb(e.__traceback__))
            logging.error(f"update video failed {type(e)} {e}\n{traceback_str}")
            await video.fail(f"update video failed {type(e)} {e}")
