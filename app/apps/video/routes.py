import logging
import uuid

from apps.video.models import Video
from apps.video.schemas import (
    VideoCreateSchema,
    VideoEngines,
    VideoEnginesSchema,
    VideoSchema,
    VideoWebhookData,
)
from apps.video.services import process_video_webhook
from fastapi import BackgroundTasks, Request
from fastapi_mongo_base.routes import AbstractTaskRouter
from usso.fastapi import jwt_access_security
from utils import finance


class VideoRouter(AbstractTaskRouter[Video, VideoSchema]):
    def __init__(self):
        super().__init__(
            model=Video,
            user_dependency=jwt_access_security,
            schema=VideoSchema,
            tags=["Video"],
            # prefix="",
        )

    def config_routes(self, **kwargs):
        super().config_routes(update_routes=False, **kwargs)
        self.router.add_api_route(
            "/{uid:uuid}/webhook",
            self.webhook,
            methods=["POST"],
            status_code=200,
        )

    async def create_item(
        self,
        request: Request,
        data: VideoCreateSchema,
        background_tasks: BackgroundTasks,
    ):
        item: Video = await super(AbstractTaskRouter, self).create_item(request, data)
        await finance.check_quota(item)
        item.task_status = "init"
        background_tasks.add_task(item.start_processing)
        return item

    async def webhook(self, request: Request, uid: uuid.UUID, data: VideoWebhookData):
        logging.info(f"Webhook for video {uid}, {data=}")
        item: Video = await self.get_item(uid, user_id=None)
        if item.status == "cancelled":
            return {"message": "Video has been cancelled."}
        await process_video_webhook(item, data)
        return {}


router = VideoRouter().router


@router.get("/engines")
async def engines():
    engines = [
        VideoEnginesSchema.from_model(engine)
        for engine in VideoEngines
        if engine != VideoEngines.runway
    ]
    return engines
